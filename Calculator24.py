import time
import threading
import sys
import mido
from scapy.all import conf, Ether, Raw

INTERFACE = "Network_Card_Name_Here" # La tua interfaccia Arch
MAC_CONSOLE = "Insert_MAC_Address_Here"

print("===============================================================")
print(" Calculator|24 - Calculator for the DigiDesign Control|24      ")
print(" By Davitek (With the small help of Gemini and Wireshark ;) )  ")
print("===============================================================")

try:
    sock = conf.L2socket(iface=INTERFACE)
except Exception as e:
    print(f"Network Error: {e}", "Did you config everything correctly? Are you running as root?")
    sys.exit(1)

cmd_seq = 1
rx_mixer_seq = 0
seq_lock = threading.Lock()
parser = mido.Parser()
threads_started = False

TRANSPORT_FONT = {
    '0': 0x7e, '1': 0x30, '2': 0x6d, '3': 0x79, '4': 0x33,
    '5': 0x5b, '6': 0x5f, '7': 0x70, '8': 0x7f, '9': 0x7b,
    ' ': 0x00, '-': 0x01, 'E': 0x4f, 'r': 0x05
}

calc_input = "0"
calc_stored = None
calc_op = None
calc_reset = True
last_val = None
last_op = None

def send_eth_cmd(cmd_hex, extra_data=b""):
    global cmd_seq
    length = 16 + len(extra_data)
    payload = bytearray(max(46, length))
    payload[0:2] = length.to_bytes(2, 'big')
    with seq_lock:
        payload[4:8] = cmd_seq.to_bytes(4, 'big')
        payload[14:16] = bytes.fromhex(cmd_hex)
        if extra_data:
            payload[16:16+len(extra_data)] = extra_data
        pkt = Ether(dst=MAC_CONSOLE, type=0x885f) / Raw(load=bytes(payload))
        sock.send(pkt)
        cmd_seq += 1

def send_pong(rx_seq):
    global cmd_seq
    with seq_lock:
        payload = bytearray(46)
        payload[0:2] = b'\x00\x10'
        payload[4:8] = cmd_seq.to_bytes(4, 'big')
        payload[8:12] = rx_seq.to_bytes(4, 'big')
        payload[14:16] = b'\xa0\x00'
        pkt = Ether(dst=MAC_CONSOLE, type=0x885f) / Raw(load=bytes(payload))
        sock.send(pkt)
        cmd_seq += 1

def send_ping():
    global cmd_seq, rx_mixer_seq
    with seq_lock:
        payload = bytearray(46)
        payload[0:2] = b'\x00\x10'
        payload[4:8] = cmd_seq.to_bytes(4, 'big')
        payload[8:12] = rx_mixer_seq.to_bytes(4, 'big')
        payload[14:16] = b'\x00\x00'
        pkt = Ether(dst=MAC_CONSOLE, type=0x885f) / Raw(load=bytes(payload))
        sock.send(pkt)
        cmd_seq += 1

def ping_loop():
    while True:
        send_ping()
        time.sleep(2.5)

def write_transport(text):
    dots_byte = 0x00

    if text == "Err":
        pure_text = "     Err"
    else:
        if '.' in text:
            frac_len = len(text.split('.')[1])
            if frac_len > 0 and frac_len <= 7:
                dots_byte = 1 << (7 - frac_len)
            pure_text = text.replace('.', '')
        else:
            pure_text = text

        pure_text = pure_text.rjust(8, ' ')

    reversed_text = pure_text[::-1]

    tc_hardware_bytes = bytearray()
    for char in reversed_text:
        tc_hardware_bytes.append(TRANSPORT_FONT.get(char, 0x00))

    # SICURA HARDWARE: Tagliamo a 8 byte esatti per impedire il blocco del SysEx
    tc_hardware_bytes = tc_hardware_bytes[:8]

    sysex_tr = bytearray.fromhex("f0 13 01 30 19")
    sysex_tr.append(dots_byte)
    sysex_tr.extend(tc_hardware_bytes)
    sysex_tr.append(0xF7)

    send_eth_cmd("0023", sysex_tr)

def format_math_result(res):
    if res == "Err": return "Err"

    if isinstance(res, float) and res.is_integer():
        res = int(res)

    res_str = str(res)

    if 'e' in res_str.lower():
        return "Err"

    int_part = res_str.split('.')[0]
    if len(int_part) > 8:
        return "Err"

    if '.' in res_str:
        allowed = ""
        slots = 0
        for c in res_str:
            allowed += c
            if c != '.':
                slots += 1
            if slots == 8:
                break

        if allowed.endswith('.'):
            allowed = allowed[:-1]
        return allowed

    return res_str

def draw_signature_on_faders():
    testo = "Calculator 24 | By Davitek"
    testo_centrato = testo.center(96, ' ')

    for i in range(24):
        chunk = testo_centrato[i*4 : (i+1)*4]
        addr = 0x20 + i
        sysex = bytearray.fromhex(f"f0 13 01 40 {addr:02x} 00")
        sysex.extend(chunk.encode('ascii'))
        sysex.append(0xF7)
        send_eth_cmd("0023", sysex)
        time.sleep(0.01)

def handle_calculator_key(key):
    global calc_input, calc_stored, calc_op, calc_reset, last_val, last_op

    # 1. INSERIMENTO NUMERI E PUNTO
    if key in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.']:
        if calc_reset:
            calc_input = ""
            calc_reset = False

        if key == '.' and '.' in calc_input:
            return

        slots_count = len(calc_input.replace('.', '').replace('-', ''))
        if key != '.' and slots_count >= 8:
            calc_input = "Err"
            calc_stored = None
            calc_op = None
            last_op = None
            last_val = None
            calc_reset = True
            write_transport("Err")
            print("Overflow! Result was more than 8 digits!")
            return

        if key == '.' and calc_input in ["", "-"]:
            calc_input += "0"

        calc_input += key
        write_transport(calc_input)
        print(f"🔹 Input: {calc_input}")

    # 2. CAMBIO SEGNO (+/-) -> Tasto ENTER
    elif key == '+/-':
        if calc_input != "0" and calc_input != "Err":
            if calc_input.startswith('-'):
                # Toglie il meno
                calc_input = calc_input[1:]
            else:
                # Aggiunge il meno (se c'è spazio fisico)
                slots_count = len(calc_input.replace('.', ''))
                if slots_count < 8:
                    calc_input = '-' + calc_input
                else:
                    print("Cannot add minus symbol! Out of screen.")
                    return

            write_transport(calc_input)
            print(f"Swapped sign: {calc_input}")

    # 3. OPERATORI (+, -, *, /)
    elif key in ['+', '-', '*', '/']:
        if not calc_reset and calc_op and calc_stored is not None:
            try:
                val1 = calc_stored
                val2 = float(calc_input)
                if calc_op == '+': res = val1 + val2
                elif calc_op == '-': res = val1 - val2
                elif calc_op == '*': res = val1 * val2
                elif calc_op == '/': res = val1 / val2 if val2 != 0 else "Err"

                res_str = format_math_result(res)

                if res_str != "Err":
                    calc_stored = float(res_str)
                    calc_input = res_str
                else:
                    calc_stored = None
                    calc_input = "Err"

                write_transport(calc_input)
            except Exception:
                pass

        if calc_input != "Err":
            calc_stored = float(calc_input)

        calc_op = key
        calc_reset = True
        print(f"🔸 Operator: {calc_op} | Last Value: {calc_stored}")

    # 4. TASTO UGUALE (=)
    elif key == '=':
        try:
            if calc_op:
                val1 = calc_stored
                val2 = float(calc_input) if not calc_reset else val1
                op = calc_op
            elif last_op and last_val is not None:
                val1 = float(calc_input)
                val2 = last_val
                op = last_op
            else:
                return

            if op == '+': res = val1 + val2
            elif op == '-': res = val1 - val2
            elif op == '*': res = val1 * val2
            elif op == '/': res = val1 / val2 if val2 != 0 else "Err"

            res_str = format_math_result(res)

            write_transport(res_str)
            print(f"Result: {res_str}")

            calc_input = res_str
            calc_stored = float(res_str) if res_str != "Err" else None
            last_val = val2
            last_op = op
            calc_op = None
            calc_reset = True

        except Exception:
            write_transport("Err")
            calc_input = "0"
            calc_stored = None
            calc_op = None
            last_op = None
            last_val = None
            calc_reset = True

    # 5. TASTO CLEAR (C)
    elif key == 'C':
        calc_input = "0"
        calc_stored = None
        calc_op = None
        last_op = None
        last_val = None
        calc_reset = True
        write_transport(calc_input)
        print("Screen and memory cleared.")

def init_sequence():
    global threads_started
    print("Handshaking with mixer...")
    for _ in range(5):
        send_eth_cmd("e200", b"\x00\x00\x00\x00")
        time.sleep(0.005)

    if not threads_started:
        threading.Thread(target=ping_loop, daemon=True).start()
        threads_started = True

    time.sleep(0.5)
    write_transport("0")
    draw_signature_on_faders()

print("Waiting for mixer...")
is_online = False

while True:
    try:
        pkt = sock.recv()
        if pkt and pkt.haslayer(Ether) and pkt[Ether].src.lower() == MAC_CONSOLE:
            if pkt.haslayer(Raw):
                data = pkt[Raw].load
                if len(data) < 16:
                    continue

                length_field = data[0:2]
                if length_field == b'\x00\x32':
                    if not is_online:
                        init_sequence()
                        is_online = True
                        print("\nMixer Online!\n")
                    continue

                cmd = data[14:16]
                rx_mixer_seq = int.from_bytes(data[4:8], 'big')

                if cmd not in [b'\x00\x00', b'\xa0\x00']:
                    send_pong(rx_mixer_seq)

                if cmd in [b'\x00\x01', b'\x00\x02', b'\x00\x13', b'\x00\x23']:
                    total_len = int.from_bytes(length_field, 'big')
                    payload_intero = data[16:total_len]

                    if payload_intero:
                        parser.feed(payload_intero)
                        for msg in parser:
                            if msg.type == 'note_on' and msg.velocity == 90:
                                note = msg.note
                                if 0 <= note <= 9:     handle_calculator_key(str(note))
                                elif note == 10:       handle_calculator_key('C')
                                elif note == 11:       handle_calculator_key('=')
                                elif note == 12:       handle_calculator_key('/')
                                elif note == 13:       handle_calculator_key('*')
                                elif note == 14:       handle_calculator_key('-')
                                elif note == 15:       handle_calculator_key('+')
                                elif note == 16:       handle_calculator_key('.')
                                elif note == 17:       handle_calculator_key('+/-') # ENTER trasforma in negativo

    except Exception as e:
        pass
