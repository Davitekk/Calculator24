# Calculator24
Calculator for the Digidesign Control|24 Mixer/Console.

Works like a normal calculator, use the numpad on the mixer to insert numbers, press entoer to change the number from positive to negative.
This code has been only tested with a direct LAN connection from the computer to the console, no switches or routers, only a LAN Cable.

### This code has been tested on Linux and MacOS only.

# Installation and Setup

- Install Python 3.8 or higher
- Clone this repository
- Install Pyton requirements: 
`pip install -r requirements.txt`
- Insert your Ethernet card name and Control|24 MAC Address on line 7 and 8 of the Python script
- You can find your Ethernet card name by doing `ifconfig` in a terminal.
- You can find your Control|24 Console MAC Address by going in: `Utilities > Sys Info`
- Hold the button and Write down the Ethernet ID Value, you can press the Utility button once to make the writing persist, reboot the mixer to exit out of the Sys Info Menu.
- Connect your Control|24 Console to your PC via LAN if not done already.
- Run the script as root
- Enjoy :)

This project was made for fun while trying to reverse engineer the Digidesign LAN protocol to make this console work on recent pro tools versions with open source code. (Still WIP)

I will not be focusing on this project right now as i am focusing on reverse engineering every part of this mixer.
When i am finished (or just give up idk) i will add more silly stuff in this code :)

## TODO

- Add some crazy ways to do calculations
- Use other parts of the mixer as displays
- I have no idea anymore
