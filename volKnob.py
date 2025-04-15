import time
import board
import busio
import digitalio
import rotaryio
import adafruit_ssd1306
import usb_hid
import neopixel  # Added for RGB LED support
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_framebuf import BitmapFont

# OLED display configuration
OLED_WIDTH = 128
OLED_HEIGHT = 64

# Initialize I2C for YD-RP2040
i2c = busio.I2C(scl=board.GP5, sda=board.GP4)
oled = adafruit_ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=0x3C)
font = BitmapFont("font5x8.bin")

# Initialize USB HID interfaces
kbd = Keyboard(usb_hid.devices)
cc = ConsumerControl(usb_hid.devices)

# Initialize keyboard layout for text entry
keyboard_layout = KeyboardLayoutUS(kbd)

# Initialize the on-board RGB LED at GP23
pixel = neopixel.NeoPixel(board.GP23, 1, brightness=0.3, auto_write=False)

# Define colors for each layer (RGB format)
layer_colors = [
    (255, 0, 0),    # Red for Layer 1 (MC)
    (0, 255, 0),    # Green for Layer 2 (Vim)
    (0, 0, 255),    # Blue for Layer 3 (3D)
    (255, 255, 0),  # Yellow for Layer 4 (VS)
    (255, 0, 255),  # Magenta for Layer 5 (LX)
    (0, 255, 255)   # Cyan for Layer 6 (X86)
]

# Function to update RGB LED based on active layer
def update_led_color():
    pixel[0] = layer_colors[current_layer]
    pixel.show()

# Configure input pins for YD-RP2040
switch_pins = [board.GP0, board.GP1, board.GP2, board.GP3, board.GP6,
               board.GP7, board.GP12, board.GP13, board.GP14]
switches = [digitalio.DigitalInOut(pin) for pin in switch_pins]
for switch in switches:
    switch.direction = digitalio.Direction.INPUT
    switch.pull = digitalio.Pull.UP

# Configure rotary encoders
rotary1 = rotaryio.IncrementalEncoder(board.GP16, board.GP15)
rotary2 = rotaryio.IncrementalEncoder(board.GP11, board.GP10)
button1 = digitalio.DigitalInOut(board.GP17)
button2 = digitalio.DigitalInOut(board.GP9)
button1.direction = digitalio.Direction.INPUT
button1.pull = digitalio.Pull.UP
button2.direction = digitalio.Direction.INPUT
button2.pull = digitalio.Pull.UP

# Custom names for each layer
layer_names = [
    "MC",  # Layer 1 - Media controls
    "Vim", # Layer 2 - Vim commands
    "3D",  # Layer 3 - S-Z and numbers
    "VS",  # Layer 4 - Numbers
    "LX",  # Layer 5 - Function keys
    "X86"  # Layer 6 - Modifiers
]

# Add classes to differentiate between keyboard keys, media controls, and key combos
class MediaControl:
    def __init__(self, control_code):
        self.code = control_code

class KeyCombo:
    def __init__(self, *keys, label=None):
        self.keys = keys
        self.label = label  # Custom display label

# New class for string macros
class MacroString:
    def __init__(self, string_to_type, label=None, add_enter=False):
        self.string = string_to_type
        self.label = label or string_to_type
        self.add_enter = add_enter  # Add Enter key at end if True

# Layer definitions (keyboard shortcuts)
layers = [
    # Layer 1 with media controls and common key combos
    [MediaControl(ConsumerControlCode.VOLUME_DECREMENT),
     MediaControl(ConsumerControlCode.VOLUME_INCREMENT),
     MediaControl(ConsumerControlCode.MUTE),
     KeyCombo(Keycode.GUI, Keycode.SPACE, label="Spot"),
     KeyCombo(Keycode.GUI, Keycode.C, label="Copy"),
     KeyCombo(Keycode.GUI, Keycode.V, label="Paste"),
     KeyCombo(Keycode.GUI, Keycode.X, label="Cut"),
     KeyCombo(Keycode.GUI, Keycode.Z, label="Undo"),
     KeyCombo(Keycode.GUI, Keycode.TAB, label="App")],

    # Layer 2 - Vim commands
    [MacroString(":wq", label=":wq"),
     MacroString(":q!", label=":q!"),
     MacroString(":wq\n", label=":wq n"),  # With Enter key
     MacroString("i", label="Ins1"),
     MacroString("dd", label="-line"),
     MacroString("yy", label="Yank"),
     MacroString("p", label="Paste"),
     MacroString("u", label="Undo"),
     MacroString("G", label="Bottom")],

    # Layer 3
    [Keycode.S, Keycode.T, Keycode.U, Keycode.V, Keycode.W, Keycode.X, Keycode.Y, Keycode.Z, Keycode.ONE],

    # Layer 4
    [Keycode.TWO, Keycode.THREE, Keycode.FOUR, Keycode.FIVE, Keycode.SIX, Keycode.SEVEN, Keycode.EIGHT, Keycode.NINE, Keycode.ZERO],

    # Layer 5
    [Keycode.F1, Keycode.F2, Keycode.F3, Keycode.F4, Keycode.F5, Keycode.F6, Keycode.F7, Keycode.F8, Keycode.F9],

    # Layer 6 with more key combos
    [Keycode.F10,
     MediaControl(ConsumerControlCode.VOLUME_DECREMENT),
     MediaControl(ConsumerControlCode.VOLUME_INCREMENT),
     KeyCombo(Keycode.GUI, Keycode.Q, label="Quit App"),
     KeyCombo(Keycode.GUI, Keycode.W, label="Close Win"),
     KeyCombo(Keycode.GUI, Keycode.ALT, Keycode.ESCAPE, label="ForceQuit"),
     Keycode.SHIFT, Keycode.CONTROL, Keycode.ALT]
]

# Track state
current_layer = 0
selected_layer = 0
last_position_layer = 0
last_position_volume = 0

# Helper function to draw text using the font
def draw_text(text, x, y):
    for i, char in enumerate(text):
        font.draw_char(char, x + i * 6, y, oled, 1)

# Helper function to underline text
def underline_text(text, x, y, is_underlined=False):
    draw_text(text, x, y)
    if is_underlined:
        for i in range(len(text) * 6):
            oled.pixel(x + i, y + 10, 1)

# Keycode to display string converter
def keycode_to_string(key):
    if isinstance(key, MediaControl):
        media_dict = {
            ConsumerControlCode.VOLUME_INCREMENT: "Vol+",
            ConsumerControlCode.VOLUME_DECREMENT: "Vol-",
            ConsumerControlCode.MUTE: "Mute"
            # Add other media controls as needed
        }
        return media_dict.get(key.code, "???")
    elif isinstance(key, KeyCombo):
        # Use custom label if provided
        if key.label:
            return key.label
        
        # Otherwise generate a default label
        key_names = []
        for k in key.keys:
            if k == Keycode.GUI:
                key_names.append("Cmd")
            elif k == Keycode.SHIFT:
                key_names.append("Shft")
            elif k == Keycode.ALT:
                key_names.append("Opt")
            elif k == Keycode.CONTROL:
                key_names.append("Ctrl")
            elif k == Keycode.SPACE:
                key_names.append("Spc")
            elif k == Keycode.TAB:
                key_names.append("Tab")
            elif k == Keycode.ESCAPE:
                key_names.append("Esc")
            elif k == Keycode.C:
                key_names.append("C")
            elif k == Keycode.V:
                key_names.append("V")
            elif k == Keycode.X:
                key_names.append("X")
            elif k == Keycode.Z:
                key_names.append("Z")
            elif k == Keycode.Q:
                key_names.append("Q")
            elif k == Keycode.W:
                key_names.append("W")
            else:
                # For other keys, use a generic representation
                key_names.append("?")
        return "+".join(key_names)
    elif isinstance(key, MacroString):
        # Return the custom label for the macro string
        return key.label
    else:
        # Your existing keycode dictionary
        keycode_dict = {
            Keycode.C: "C", Keycode.D: "D",
            Keycode.E: "E", Keycode.F: "F", Keycode.G: "G", Keycode.H: "H",
            Keycode.I: "I", Keycode.J: "J", Keycode.K: "K", Keycode.L: "L",
            Keycode.M: "M", Keycode.N: "N", Keycode.O: "O", Keycode.P: "P",
            Keycode.Q: "Q", Keycode.R: "R", Keycode.S: "S", Keycode.T: "T",
            Keycode.U: "U", Keycode.V: "V", Keycode.W: "W", Keycode.X: "X",
            Keycode.Y: "Y", Keycode.Z: "Z", Keycode.ONE: "1", Keycode.TWO: "2",
            Keycode.THREE: "3", Keycode.FOUR: "4", Keycode.FIVE: "5",
            Keycode.SIX: "6", Keycode.SEVEN: "7", Keycode.EIGHT: "8",
            Keycode.NINE: "9", Keycode.ZERO: "0", Keycode.F1: "F1",
            Keycode.F2: "F2", Keycode.F3: "F3", Keycode.F4: "F4",
            Keycode.F5: "F5", Keycode.F6: "F6", Keycode.F7: "F7",
            Keycode.F8: "F8", Keycode.F9: "F9", Keycode.F10: "F10",
            Keycode.F11: "F11", Keycode.F12: "F12", Keycode.ESCAPE: "ESC",
            Keycode.TAB: "TAB", Keycode.CAPS_LOCK: "CAPS", Keycode.SHIFT: "SHIFT",
            Keycode.CONTROL: "CTRL", Keycode.ALT: "ALT"
        }
        return keycode_dict.get(key, "???")

# Update the display
def update_display():
    oled.fill(0)

    # Calculate optimal spacing for layer tabs
    tab_width = 128 // len(layers)

    # Draw layer tabs with custom names
    for layer_index in range(len(layers)):
        name = layer_names[layer_index]
        # Center the text within its tab area
        x_pos = layer_index * tab_width + (tab_width - len(name) * 6) // 2
        underline_text(name, x_pos, 0,
                      is_underlined=(selected_layer == layer_index))

        # No vertical separators between tabs as requested

    # Display key assignments
    header_height = 20
    row_height = 11

    for i, keycode in enumerate(layers[current_layer]):
        x = (i % 3) * 40
        y = (i // 3) * row_height + header_height
        draw_text(keycode_to_string(keycode), x, y)

    oled.show()

# Initialize display and LED
update_display()
update_led_color()  # Initialize the RGB LED color

# Main loop
while True:
    # Layer selection with rotary encoder 2
    position_layer = rotary2.position
    new_selected_layer = position_layer % len(layers)
    if new_selected_layer != selected_layer:
        selected_layer = new_selected_layer
        update_display()

    # Apply selected layer when button is pressed
    if not button2.value:
        current_layer = selected_layer
        update_display()
        update_led_color()  # Update LED color when layer changes
        time.sleep(0.2)  # Debounce delay

    # Volume control with rotary encoder 1
    position_volume = rotary1.position
    if position_volume > last_position_volume:
        cc.send(ConsumerControlCode.VOLUME_INCREMENT)
    elif position_volume < last_position_volume:
        cc.send(ConsumerControlCode.VOLUME_DECREMENT)
    last_position_volume = position_volume

    # Mute toggle
    if not button1.value:
        cc.send(ConsumerControlCode.MUTE)
        time.sleep(0.2)  # Debounce delay

    # Check buttons and send keypresses
    for i, switch in enumerate(switches):
        if not switch.value:
            key = layers[current_layer][i]
            if isinstance(key, MediaControl):
                cc.send(key.code)  # Send as media control
            elif isinstance(key, KeyCombo):
                kbd.send(*key.keys)  # Send all keys in the combination
            elif isinstance(key, MacroString):
                # Use keyboard_layout to type the string
                keyboard_layout.write(key.string)
                if key.add_enter:
                    kbd.send(Keycode.ENTER)
            else:
                kbd.send(key)  # Send as keyboard key

            # Wait for button release to prevent repeated presses
            while not switch.value:
                pass

    time.sleep(0.01)  # Small delay to prevent CPU overuse
