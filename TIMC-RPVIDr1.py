from MainGUIr0 import Ui_MainWindow
from PyQt5 import QtWidgets as qtw
from PyQt5 import QtCore as qtc
from PyQt5 import QtGui as qtg
from XInput import *
from simple_pid import PID
import sys
import gclib

# Backward and Forward Software Limits
BL = -2147483648
FL = 2147483647

PYINSTALLER = True
DEBUG = False


class VegaCard():
    def __init__(self, gui_input, io_input):
        self.high_gain = gui_input[0]
        self.medium_gain = gui_input[1]
        self.low_gain = gui_input[2]
        self.reset = gui_input[3]
        self.signal_high = gui_input[4]
        self.signal_low = gui_input[5]
        self.timeout = gui_input[6]
        self.fault_status = gui_input[7]
        self.jumper_6 = io_input[0]
        self.jumper_11 = io_input[1]
        self.jumper_12 = io_input[2]
        self.fault_pin = io_input[3]
        self.high_pin = io_input[4]
        self.low_pin = io_input[5]
        self.timeout_pin = io_input[6]
        self.connection = Galil_Widget()
        self.update_signals = ThreadDataFetch(['MG @IN[' + self.fault_pin + ']',
                                               'MG @IN[' + self.high_pin + ']',
                                               'MG @IN[' + self.low_pin + ']',
                                               'MG @IN[' + self.timeout_pin + ']'], "scan vega")
        self.update_signals.received_data.connect(self.update_diagnostics)
        self.update_signals.start()

        self.high_gain.toggled.connect(self.set_gain)
        self.medium_gain.toggled.connect(self.set_gain)
        self.low_gain.toggled.connect(self.set_gain)
        self.reset.pressed.connect(self.reset_vega)
        self.vega_has_faulted = False

    def set_gain(self):
        if self.high_gain.isChecked():
            self.connection.gcmd('CB ' + self.jumper_11)
            self.connection.gcmd('CB ' + self.jumper_12)
        elif self.medium_gain.isChecked():
            self.connection.gcmd('CB ' + self.jumper_11)
            self.connection.gcmd('SB ' + self.jumper_12)
        elif self.low_gain.isChecked():
            self.connection.gcmd('SB ' + self.jumper_11)
            self.connection.gcmd('CB ' + self.jumper_12)

    def reset_vega(self):
        # Check the bit state, if it is set the output will be 1
        bit_state = int(float(self.connection.gcmd('MG @OUT[' + self.jumper_6 + ']')))
        # If the bit state, there is a reset in process. Stop the reset by clearing the reset bit
        if bit_state:
            self.connection.gcmd('CB' + self.jumper_6)
            self.reset.setEnabled(True)
        # A reset is not in process, set the reset bit and check back later to turn it off
        else:
            self.connection.gcmd('SB' + self.jumper_6)
            self.reset.setEnabled(False)
            qtc.QTimer.singleShot(600, self.reset_vega)

    def update_diagnostics(self, data):
        # Fault,High,Low, Timeout
        # Check if there is a fault
        if int(float(data[0])):
            self.fault_status.setStyleSheet("background-color: red;\nfont: 10pt \"MS Shell Dlg 2\";")
            self.vega_has_faulted = True
        else:
            self.fault_status.setStyleSheet("")
            self.fault_status.setStyleSheet("font: 10pt \"MS Shell Dlg 2\";")
            self.vega_has_faulted = False
        # Check if there is a high signal
        if int(float(data[1])):
            self.signal_high.setStyleSheet("background-color: red;\nfont: 10pt \"MS Shell Dlg 2\";")
        else:
            self.signal_high.setStyleSheet("")
            self.signal_high.setStyleSheet("font: 10pt \"MS Shell Dlg 2\";")
        # Check if there is a low signal
        if int(float(data[2])):
            self.signal_low.setStyleSheet("background-color: red;\nfont: 10pt \"MS Shell Dlg 2\";")
        else:
            self.signal_low.setStyleSheet("")
            self.signal_low.setStyleSheet("font: 10pt \"MS Shell Dlg 2\";")
        # Check if there has been a timeout
        if int(float(data[2])):
            self.timeout.setStyleSheet("background-color: red;\nfont: 10pt \"MS Shell Dlg 2\";")
        else:
            self.timeout.setStyleSheet("")
            self.timeout.setStyleSheet("font: 10pt \"MS Shell Dlg 2\";")

    def report_fault(self):
        return self.vega_has_faulted


class VaredanFaults():
    def __init__(self, button: qtw.QPushButton, checkboxes: [qtw.QCheckBox]):
        self.checkboxes = checkboxes
        self.button = button
        self.button.pressed.connect(self.clear_faults)
        self.varedan_error_list = ["Alarm = BUS UV",
                                   "Alarm = RMS OC",
                                   "Alarm = ABS OC",
                                   "Alarm = AMP OT",
                                   "Alarm = DSP   ",
                                   "Alarm = SOA   ",
                                   "Alarm = NVM   ",
                                   "Alarm = AUTOBL",
                                   "Alarm = HALLS ",
                                   "Alarm = FATAL ",
                                   "Alarm = BUS OV",
                                   "Alarm = MOT OT",
                                   "Alarm = 5V REF",
                                   "Alarm = 15VREF",
                                   "Alarm = 2.5REF",
                                   "Alarm = 5V EXT",
                                   "Alarm = None  "
                                   ]

    def clear_faults(self):
        for i in range(len(self.checkboxes)):
            self.checkboxes[i].setChecked(False)
            font = qtg.QFont()
            font.setBold(False)
            font.setWeight(50)
            self.checkboxes[i].setFont(font)

    def process_serial_string(self, data):
        self.clear_faults()
        # print("data:", repr(data))
        for i in range(len(self.varedan_error_list)):
            if self.varedan_error_list[i] in data:
                self.set_fault(i)

    def set_fault(self, index):
        self.checkboxes[index].setChecked(True)
        font = qtg.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.checkboxes[index].setFont(font)


class Galil_Widget(qtc.QThread):
    reported_error_message = qtc.pyqtSignal(str)
    connection_count = 0

    def __init__(self):
        super(Galil_Widget, self).__init__()
        self.g = gclib.py()
        self.index = -1
        self.connection_is_opened = False
        self.open()

    def gcmd(self, cmd):
        if not self.connection_is_opened:
            self.open()
        # if self.connection_is_opened:
        try:
            result = self.g.GCommand(cmd)
            return result
        except gclib.GclibError as e:
            if str(e) == 'question mark returned by controller':
                print_statment = str(self.index) + ") DMC Error: " + str(self.g.GCommand('TC1')) + ", CMD:" + str(cmd)
                self.reported_error_message.emit(print_statment)
            else:
                print('Unexpected gclib Error:', e)

    def open(self):
        try:
            self.g.GOpen('192.168.42.100 -s ALL')
            if self.index == -1:
                Galil_Widget.connection_count += 1
                self.index = Galil_Widget.connection_count
            if DEBUG:
                print("Galil Connection", self.index, "successful")
            self.connection_is_opened = True
        except gclib.GclibError as e:
            print("Error making Galil Connection", Galil_Widget.connection_count, e)
            self.connection_is_opened = False

    def close(self):
        self.g.GClose()
        if DEBUG:
            print("Closing Connection", self.index)
        Galil_Widget.connection_count -= 1
        self.connection_is_opened = False


class NonNullEdits:
    def __init__(self, edit: qtw.QLineEdit):
        self.edit = edit
        self.edit_validator = qtg.QDoubleValidator()
        self.edit_validator.setNotation(self.edit_validator.StandardNotation)
        self.edit.setValidator(self.edit_validator)
        self.edit.textChanged.connect(self.comma_check)
        self.comma_check()
        self.incomplete_check()

    def comma_check(self, text_input=""):
        # If there is a comma remove it from the text
        if "," in text_input:
            text = self.edit.text()
            text = text.replace(',', "")
            self.edit.setText(text)

    def incomplete_check(self):
        # Don't allow for no text
        if self.edit.text() == "" or self.edit.text() == "." or self.edit.text() == "-" or self.edit.text() == "+":
            self.edit.setText("0.00")


class ApplyEdits:
    def __init__(self, edit: qtw.QLineEdit):
        self.edit = edit
        self.edit.textChanged.connect(self.undo_apply)

    def undo_apply(self):
        self.edit.setStyleSheet("background-color: white")


class BalanceWithEdit:
    def __init__(self, slider: qtw.QSlider, edit: qtw.QLineEdit):
        self.slider = slider
        self.edit = edit
        self.edit.textChanged.connect(self.update_slider)
        self.slider.valueChanged.connect(self.update_text)
        self.validator = qtg.QDoubleValidator()
        self.validator.setRange(self.slider.minimum(), self.slider.maximum(), 0)
        self.validator.setNotation(self.validator.StandardNotation)
        self.edit.setValidator(self.validator)
        self.slider.setValue(0)

    def check_if_valid(self):
        text = self.edit.text()
        if text == "" or text == "-" or text == "+" or text == ".":
            return False
        if text.count(".") > 1:
            return False
        if text[len(text) - 1] == ".":
            return False
        return True

    def update_slider(self):
        if not self.check_if_valid():
            self.slider.setValue(0)
        else:
            self.slider.setValue(int(self.edit.text()))

    def update_text(self):
        self.edit.setText(str('{:.0f}'.format(self.slider.value())))

    def disable(self):
        self.slider.setEnabled(False)
        self.edit.setEnabled(False)

    def enable(self):
        self.slider.setEnabled(True)
        self.edit.setEnabled(True)


class SliderWithEdit:
    def __init__(self, slider: qtw.QSlider, edit: qtw.QLineEdit, max_allowed):
        self.slider = slider
        self.edit = edit
        self.max_allowed = max_allowed  # Inches or Amps
        self.conversion_factor = self.slider.maximum() / max_allowed  # Slider Counts/tool units
        self.edit.textChanged.connect(self.update_slider)  # Updates slider right away with each new number
        self.slider.valueChanged.connect(self.update_text)
        self.validator = qtg.QDoubleValidator()
        self.validator.setRange(0, self.max_allowed, 2)
        self.validator.setNotation(self.validator.StandardNotation)
        self.edit.setValidator(self.validator)
        self.edit.setText(str(2.00))

    # Update the slider to be the value from the text box edited by the user
    def update_slider(self):
        if self.edit.text() != "" and self.edit.text() != "." and self.edit.text() != "+" and self.edit.text() != "-":
            if 0 < float(self.edit.text()) <= self.max_allowed:
                self.slider.setValue(int(float(self.edit.text()) * self.conversion_factor))
            elif float(self.edit.text()) > self.max_allowed:
                self.slider.setValue(self.slider.maximum())
                self.edit.setText(str(self.max_allowed) + "0")
            elif self.edit.text() == "0.00":
                self.slider.setValue(self.slider.minimum())
            elif self.edit.text() == "0" or self.edit.text() == "00" or self.edit.text() == "0.0" or self.edit.text() == "0.":
                self.slider.setValue(self.slider.minimum())

    # Update the text when the slider bar has been moved
    def update_text(self):
        text = round(self.slider.value() / self.conversion_factor, 2)
        self.edit.setText(str('{:.2f}'.format(text)))

    # Return the converted value of the slider bar in units: inches/sec
    def value(self):
        rv = self.slider.value() / self.conversion_factor
        return rv

    def update_conversion_factor(self):
        self.conversion_factor = self.slider.maximum() / self.max_allowed

    def disable(self):
        self.slider.setEnabled(False)
        self.edit.setEnabled(False)

    def enable(self):
        self.slider.setEnabled(True)
        self.edit.setEnabled(True)


def is_active(voltage):
    min_v = 0.5
    max_v = 4.5
    test = round(float(voltage), 2)
    if min_v < test < max_v:
        return True
    else:
        return False


def is_sat_min(voltage):
    min_v = 0.5
    test = round(float(voltage), 2)
    if test < min_v:
        return True
    else:
        return False


def is_sat_max(voltage):
    max_v = 4.5
    test = round(float(voltage), 2)
    if test > max_v:
        return True
    else:
        return False


def voltage_to_degree(voltage, orientation):
    voltage = round(float(voltage), 2)
    # In the right and up orientation, the sensors are pins up which is not correct, invert output and apply correction
    if orientation == "RIGHT" or orientation == "UP":
        degree = round(8.222 * voltage - 20.522, 4)
        degree *= -1
    # In the left and down orientation, the sensors are pins down which is correct. Apply standard conversion
    else:
        degree = round(20 * (voltage - 2.5) / 1.5, 4)
    return '{:.2f}'.format(degree)


class UserWindow(qtw.QMainWindow, Ui_MainWindow):
    count = 0
    restore_index_speed_sent = qtc.pyqtSignal(float)
    restore_scan_speed_sent = qtc.pyqtSignal(float)
    gamepad_enabled_for_index = qtc.pyqtSignal(bool)
    gamepad_enabled_for_scan = qtc.pyqtSignal(bool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        # Setup the edit boxes so the user can't enter bad information
        self.myEdits = []
        edits = [self.set_index_position_edit,
                 self.move_index_to_edit,
                 self.set_scan_position_edit,
                 self.move_scan_to_edit,
                 self.right_soft_limit_edit,
                 self.left_soft_limit_edit,
                 self.scan_options_scan_start,
                 self.scan_options_scan_stop,
                 self.scan_options_index_start,
                 self.scan_options_index_size,
                 self.scan_options_index_stop,
                 self.scan_distance_jogged,
                 self.index_distance_jogged,
                 self.scan_axis_error_limit,
                 self.follower_axis_error_limit,
                 self.left_axis_error_limit,
                 self.right_axis_error_limit,
                 self.commanded_angle,
                 self.set_scan_position_edit,
                 self.scan_axis_speed_edit,
                 self.index_axis_speed_edit,
                 self.scan_options_scan_edit,
                 self.scan_options_index_edit,
                 self.scan_axis_current_limit_edit,
                 self.index_axis_current_limit_edit,
                 self.max_scan_gamepad_speed_edit,
                 self.max_index_gamepad_speed_edit,
                 ]
        for i in range(len(edits)):
            self.myEdits.append(NonNullEdits(edits[i]))

        self.index_axis_speed_control = SliderWithEdit(self.index_axis_speed_slider, self.index_axis_speed_edit, 3.0)
        self.index_axis_balance_control = BalanceWithEdit(self.index_axis_balance_slider, self.index_balance_edit)
        self.scan_axis_speed_control = SliderWithEdit(self.scan_axis_speed_slider, self.scan_axis_speed_edit, 3.0)
        self.scan_options_scan_speed_control = SliderWithEdit(self.scan_options_scan_speed, self.scan_options_scan_edit,
                                                              3.0)
        self.scan_options_index_speed_control = SliderWithEdit(self.scan_options_index_speed,
                                                               self.scan_options_index_edit,
                                                               1.0)
        self.scan_axis_torque_control = SliderWithEdit(self.scan_axis_current_limit_slider,
                                                       self.scan_axis_current_limit_edit, 5)
        self.index_axis_torque_control = SliderWithEdit(self.index_axis_current_limit_slider,
                                                        self.index_axis_current_limit_edit, 5)
        self.scan_gamepad_speed_control = SliderWithEdit(self.max_scan_gamepad_speed_slider,
                                                         self.max_scan_gamepad_speed_edit, 3)
        self.index_gamepad_speed_control = SliderWithEdit(self.max_index_gamepad_speed_slider,
                                                          self.max_index_gamepad_speed_edit, 3)

        # Setup Left VEGA Card
        gui_input = [self.vega_left_high_gain,
                     self.vega_left_medium_gain,
                     self.vega_left_low_gain,
                     self.vega_left_reset,
                     self.vega_left_high_signal,
                     self.vega_left_low_signal,
                     self.vega_left_timeout_signal,
                     self.vega_left_fault_stauts]
        # Input pin order: jumper 6, jumper 11, jumper 12, fault, high signal, low signal, timeout signal
        io_input = ["37", "41", "42", "29", "21", "25", "17"]
        self.vega_left = VegaCard(gui_input, io_input)

        # Setup Right VEGA Card
        gui_input = [self.vega_right_high_gain,
                     self.vega_right_medium_gain,
                     self.vega_right_low_gain,
                     self.vega_right_reset,
                     self.vega_right_high_signal,
                     self.vega_right_low_signal,
                     self.vega_right_timeout_signal,
                     self.vega_right_fault_stauts]
        # Input pin order: jumper 6, jumper 11, jumper 12, fault, high signal, low signal, timeout signal
        io_input = ["38", "43", "44", "30", "22", "26", "18"]
        self.vega_right = VegaCard(gui_input, io_input)

        # Setup Scan VEGA Card
        gui_input = [self.vega_scan_high_gain,
                     self.vega_scan_medium_gain,
                     self.vega_scan_low_gain,
                     self.vega_scan_reset,
                     self.vega_scan_high_signal,
                     self.vega_scan_low_signal,
                     self.vega_scan_timeout_signal,
                     self.vega_scan_fault_stauts]
        # Input pin order: jumper 6, jumper 11, jumper 12, fault, high signal, low signal, timeout signal
        io_input = ["39", "45", "46", "31", "23", "27", "19"]
        self.vega_scan = VegaCard(gui_input, io_input)

        # Setup Follower VEGA Card
        gui_input = [self.vega_follower_high_gain,
                     self.vega_follower_medium_gain,
                     self.vega_follower_low_gain,
                     self.vega_follower_reset,
                     self.vega_follower_high_signal,
                     self.vega_follower_low_signal,
                     self.vega_follower_timeout_signal,
                     self.vega_follower_fault_stauts]
        # Input pin order: jumper 6, jumper 11, jumper 12, fault, high signal, low signal, timeout signal
        io_input = ["40", "47", "48", "32", "24", "28", "20"]
        self.vega_follower = VegaCard(gui_input, io_input)

        self.udpated_edit_0 = ApplyEdits(self.scan_axis_scaling_factor)
        self.udpated_edit_1 = ApplyEdits(self.scan_axis_error_limit)
        self.udpated_edit_2 = ApplyEdits(self.index_axis_left_scaling_factor)
        self.udpated_edit_3 = ApplyEdits(self.index_axis_right_scaling_factor)
        self.udpated_edit_4 = ApplyEdits(self.follower_scaling_factor)
        self.udpated_edit_5 = ApplyEdits(self.left_axis_error_limit)
        self.udpated_edit_6 = ApplyEdits(self.right_axis_error_limit)
        self.updated_edit_7 = ApplyEdits(self.follower_axis_error_limit)
        self.updated_edit_8 = ApplyEdits(self.kp_edit)
        self.updated_edit_9 = ApplyEdits(self.ki_edit)
        self.updated_edit_10 = ApplyEdits(self.kd_edit)

        # If the user has cleared out a line edit or left it with a minus sign and has clicked away, fill it with a 0
        app.focusChanged.connect(self.focus_changed_checks)

        # Setup Scan Axis
        self.wait_for_scan_disable = ThreadWaitForMotionComplete("C")
        self.wait_for_scan_disable.motion_completed.connect(self.turn_off_scan_motor)
        self.enable_scan_axis.pressed.connect(self.process_enable_scan)
        self.enable_scan_axis_2.pressed.connect(self.process_enable_scan)
        self.set_soft_limits.stateChanged.connect(self.process_set_soft_limits)
        self.left_soft_limit_edit.textChanged.connect(self.process_set_soft_limits)
        self.right_soft_limit_edit.textChanged.connect(self.process_set_soft_limits)
        self.jog_left.pressed.connect(self.process_jog_left)
        self.jog_left_2.pressed.connect(self.process_jog_left)
        self.jog_right.pressed.connect(self.process_jog_right)
        self.jog_right_2.pressed.connect(self.process_jog_right)
        self.jog_left.released.connect(self.stop_scan_jog)
        self.jog_left_2.released.connect(self.stop_scan_jog)
        self.jog_right.released.connect(self.stop_scan_jog)
        self.jog_right_2.released.connect(self.stop_scan_jog)
        self.stop_scan_axis.pressed.connect(self.stop_scan_jog)
        self.set_scan_position_zero.pressed.connect(self.process_set_scan_position_zero)
        self.set_scan_position_zero_2.pressed.connect(self.process_set_scan_position_zero)
        self.set_scan_position_to.pressed.connect(self.process_set_scan_position_to)
        self.move_scan_to_zero.pressed.connect(self.process_move_scan_to_zero)
        self.move_scan_to_position.pressed.connect(self.process_move_scan_to_position)
        self.scan_axis_speed_slider.valueChanged.connect(self.process_scan_axis_speed_slider_change)
        self.scan_axis_status = ThreadDataFetch(['TSC', 'MG @IN[31]'], "scan axis status")
        self.scan_axis_status.received_data.connect(self.update_scan_axis_status)
        self.scan_axis_status.refresh_wait = 0.1
        self.scan_axis_status.start()
        self.fault_scan.toggled.connect(self.process_fault_scan)

        self.scan_current_bar.setStyleSheet("background-color: black")
        self.scan_current_bar_width = self.scan_current_bar.size().width()
        self.scan_current_bar_height = self.scan_current_bar.size().height()
        pixmap = qtg.QPixmap(qtc.QSize(self.scan_current_bar_width, self.scan_current_bar_height))
        pixmap.fill(qtc.Qt.black)
        self.scan_current_bar.setPixmap(pixmap)

        # Setup Index Axis
        self.wait_for_index_disable = ThreadWaitForMotionComplete(["A", "B"])
        self.wait_for_index_disable.motion_completed.connect(self.turn_off_index_motors)
        self.enable_index_axis.pressed.connect(self.process_enable_index)
        self.enable_index_axis_2.pressed.connect(self.process_enable_index)
        self.set_index_position_zero.pressed.connect(self.process_set_index_position_zero)
        self.set_index_position_zero_2.pressed.connect(self.process_set_index_position_zero)
        self.set_index_position_to.pressed.connect(self.process_set_index_position_to)

        self.jog_index_fwd.pressed.connect(self.process_jog_index_fwd)
        self.jog_index_fwd_2.pressed.connect(self.process_jog_index_fwd)
        self.jog_index_rev.pressed.connect(self.process_jog_index_rev)
        self.jog_index_rev_2.pressed.connect(self.process_jog_index_rev)
        self.jog_index_cw.pressed.connect(self.process_jog_index_cw)
        self.jog_index_ccw.pressed.connect(self.process_jog_index_ccw)

        self.jog_index_fwd.released.connect(self.stop_index_jog)
        self.jog_index_fwd_2.released.connect(self.stop_index_jog)
        self.jog_index_rev.released.connect(self.stop_index_jog)
        self.jog_index_rev_2.released.connect(self.stop_index_jog)
        self.jog_index_cw.released.connect(self.stop_index_jog)
        self.jog_index_ccw.released.connect(self.stop_index_jog)
        self.stop_index_axis.pressed.connect(self.stop_index_jog)

        # Set Icons
        if PYINSTALLER:
            icon1 = qtg.QIcon()
            icon1.addPixmap(qtg.QPixmap(sys.prefix + "./cw.ico"), qtg.QIcon.Normal, qtg.QIcon.Off)
            self.jog_index_cw.setIcon(icon1)

            icon1 = qtg.QIcon()
            icon1.addPixmap(qtg.QPixmap(sys.prefix + "./ccw.ico"), qtg.QIcon.Normal, qtg.QIcon.Off)
            self.jog_index_ccw.setIcon(icon1)

        # Check the status of axis Right, Left, Left VEGA, Right VEGA, Follower VEGA
        self.index_axis_status = ThreadDataFetch(['TSA', 'TSB', 'MG @IN[29]', 'MG @IN[30]', 'MG @IN[32]'],
                                                 "index axis status")
        self.index_axis_status.received_data.connect(self.update_index_axis_status)
        self.index_axis_status.refresh_wait = 0.1
        self.index_axis_status.start()

        self.brake_left.pressed.connect(self.process_left_brake)
        self.brake_right.pressed.connect(self.process_right_brake)
        self.brake_right.released.connect(self.process_brake_release)
        self.brake_left.released.connect(self.process_brake_release)

        self.index_axis_balance_slider.valueChanged.connect(self.process_index_axis_speed_slider_change)
        self.index_axis_speed_slider.valueChanged.connect(self.process_index_axis_speed_slider_change)
        self.center_balance_slider.pressed.connect(lambda: self.index_axis_balance_slider.setValue(0))

        self.toggle_move_type.pressed.connect(self.process_toggle_move_type)
        self.move_index_to_zero.pressed.connect(self.process_move_index_to_zero)
        self.move_index_to_position.pressed.connect(self.process_move_index_to_position)
        self.incremental_moves = ThreadDataFetch(['MG _TPA', 'MG _TDA', 'MG _TPB'], "Incremental Move")
        self.incremental_moves.connection.reported_error_message.connect(self.error_mg.setText)
        self.incremental_moves.received_data.connect(self.update_error)

        self.fault_index.toggled.connect(self.process_fault_index)

        self.estop.pressed.connect(self.process_software_estop)

        # Left Axis current bar
        self.left_current_bar.setStyleSheet("background-color: black")
        self.left_current_bar_width = self.left_current_bar.size().width()
        self.left_current_bar_height = self.left_current_bar.size().height()
        pixmap = qtg.QPixmap(qtc.QSize(self.left_current_bar_width, self.left_current_bar_height))
        pixmap.fill(qtc.Qt.black)
        self.left_current_bar.setPixmap(pixmap)

        # Right Axis current bar
        self.right_current_bar.setStyleSheet("background-color: black")
        self.right_current_bar_width = self.right_current_bar.size().width()
        self.right_current_bar_height = self.right_current_bar.size().height()
        pixmap = qtg.QPixmap(qtc.QSize(self.right_current_bar_width, self.right_current_bar_height))
        pixmap.fill(qtc.Qt.black)
        self.right_current_bar.setPixmap(pixmap)

        # Program State Variables
        self.motor_enabled_state = False
        self.right_brake_engaged = False
        self.left_brake_engaged = False
        self.incremental_move_active = False
        self.mode_incremental_active = False
        self.mode_jogging_active = True  # GUI forces user to start in jogging mode
        self.incremental_move_in_position = False
        self.scan_axis_state = 0
        self.sign_toggled_scan_axis = False
        self.sign_toggled_index_axis = False
        self.auto_angle_is_active = False

        self.is_x_active_sensor = True
        self.orientation_state = "UP"

        self.scan_axis_is_enabled = False
        self.index_axis_is_enabled = False

        self.scan_axis_error = False
        self.index_left_axis_error = False
        self.index_right_axis_error = False
        self.hardware_estop_state = False

        self.scaling_scan_axis = 100000
        self.scaling_left_axis = 100000
        self.scaling_right_axis = 100000
        self.scaling_follower_axis = 100000
        self.allowable_following_error = 0

        self.pid = PID(20, 15, 0.01, setpoint=2.5)
        # self.pid.proportional_on_measurement = True
        self.process_pid()
        self.set_pid.pressed.connect(self.process_pid)
        self.connection = Galil_Widget()
        self.connection.reported_error_message.connect(self.error_mg.setText)

        # Configure the DMC 4040 to respond to abort
        self.gcmd('OE 3,3,3,3')
        self.gcmd('CO 12')
        self.gcmd(
            'CN ,,,,1')  # Required so that when the ESTOP button is pressed, the serial program doesn't stop running

        # Set the torque limit to 5A max commanded, LA-415 are configured to be 2A continuous, 12A instant
        self.gcmd('TL 5,5,5')
        self.follower_target = 0

        if self.connection.connection_is_opened:
            if PYINSTALLER:
                self.connection.g.GProgramDownloadFile(sys.prefix + './serial_communication.dmc', '')
            else:
                self.connection.g.GProgramDownloadFile('./serial_communication.dmc', '')
        self.stop_program.setEnabled(False)
        self.mainUpdateThread = ThreadUpdate("GUI Update")
        self.mainUpdateThread.connection.reported_error_message.connect(self.error_mg.setText)
        self.mainUpdateThread.start()
        self.mainUpdateThread.data_ready.connect(self.update_data)

        self.left_mtr_cur_avg = 0
        self.right_mtr_cur_avg = 0
        self.scan_mtr_cur_avg = 0

        self.serialThread = ThreadSerial(parent=None)
        self.serialThread.connection.reported_error_message.connect(self.error_mg.setText)
        self.serialThread.reported_serial_data.connect(self.display_serial_data)
        self.process_start_program()
        # Below updated for enclosure:
        self.inclinometer = ThreadDataFetch(['MG @AN[1]', 'MG @AN[2]'], "Inclinometer")
        self.inclinometer.connection.reported_error_message.connect(self.error_mg.setText)
        self.activateAngle.pressed.connect(self.process_activateAngle)
        self.deactivateAngle.pressed.connect(self.process_deactivateAngle)
        self.inclinometer.received_data.connect(self.process_inclinometer_data)
        # self.inclinometer.received_data.connect(lambda data: self.auto_angle_adjustment(data))
        self.inclinometer.start()
        self.angle_setpoint_slider.valueChanged.connect(self.update_setpoint)
        self.running_average_vfbk = 2.5
        self.running_average_vcmd = 2.5
        self.commanded_angle.textChanged.connect(self.process_new_commanded_angle)
        # Setup the gauge
        self.angle_readout.set_enable_value_text(False)  # Disable the output text
        self.angle_readout.set_total_scale_angle_size(180)  # pass number of degrees to the full gauge should take up

        self.start_program.pressed.connect(self.process_start_program)
        self.stop_program.pressed.connect(self.process_stop_program)
        self.help_cmds.pressed.connect(lambda: self.gcmd("MG {P2} \"H\"{^13}{N}"))
        self.reset_drive.pressed.connect(lambda: self.gcmd("MG {P2} \"R\"{^13}{N}"))
        self.clear_screen.pressed.connect(self.process_clear_screen)
        self.send_cmd.pressed.connect(self.process_send_cmd)
        self.varedan_select.currentIndexChanged.connect(self.process_varedan_select)
        self.process_varedan_select()
        self.gamepad = MyGamepadThread(self.restore_index_speed_sent, self.restore_scan_speed_sent,
                                       self.gamepad_enabled_for_index, self.gamepad_enabled_for_scan)
        self.gamepad.jogged_forward.connect(self.jog_index_fwd.pressed)
        self.gamepad.jogged_reverse.connect(self.jog_index_rev.pressed)
        self.gamepad.index_speed_updated.connect(self.process_gamepad_index_speed_updated)
        self.gamepad.differential_updated.connect(
            lambda dif: self.index_axis_balance_slider.setValue(int(self.index_axis_balance_slider.maximum() * dif)))
        self.gamepad.stopped_jog.connect(self.stop_index_jog)
        self.gamepad.left_brake_applied.connect(self.brake_left.pressed)
        self.gamepad.right_brake_applied.connect(self.brake_right.pressed)
        self.gamepad.left_brake_released.connect(self.brake_left.released)
        self.gamepad.right_brake_released.connect(self.brake_right.released)
        self.left_brake_status = ThreadDataFetch(['MG _BGA'], "Left Brake")
        self.left_brake_status.connection.reported_error_message.connect(self.error_mg.setText)
        self.left_brake_status.received_data.connect(self.process_left_brake_status)
        self.right_brake_status = ThreadDataFetch(['MG _BGB'], "Right Brake")
        self.right_brake_status.connection.reported_error_message.connect(self.error_mg.setText)
        self.right_brake_status.received_data.connect(self.process_right_brake_status)

        self.gamepad.rotated_cw.connect(self.jog_index_cw.pressed)
        self.gamepad.rotated_ccw.connect(self.jog_index_ccw.pressed)
        self.gamepad.stopped_rotation.connect(self.stop_index_jog)

        self.gamepad.jogged_left.connect(self.jog_left.pressed)
        self.gamepad.jogged_right.connect(self.jog_right.pressed)
        self.gamepad.stopped_scan.connect(self.stop_scan_jog)
        self.gamepad.scan_speed_updated.connect(self.process_gamepad_scan_speed_updated)
        self.index_axis_sign_toggle.clicked.connect(self.process_index_axis_sign_toggle)
        self.scan_axis_sign_toggle.clicked.connect(self.process_scan_axis_sign_toggle)

        self.icon_minus = qtg.QIcon()
        self.icon_plus = qtg.QIcon()
        if PYINSTALLER:
            self.icon_minus.addPixmap(qtg.QPixmap(sys.prefix + "./minus.ico"), qtg.QIcon.Normal, qtg.QIcon.Off)
            self.icon_plus.addPixmap(qtg.QPixmap(sys.prefix + "./plus.ico"), qtg.QIcon.Normal, qtg.QIcon.Off)
        else:
            self.icon_minus.addPixmap(qtg.QPixmap("Icons/minus.ico"), qtg.QIcon.Normal, qtg.QIcon.Off)
            self.icon_plus.addPixmap(qtg.QPixmap("Icons/plus.ico"), qtg.QIcon.Normal, qtg.QIcon.Off)

        self.scan_axis_sign_toggle.setIcon(self.icon_plus)
        self.index_axis_sign_toggle.setIcon(self.icon_plus)

        self.gamepad.gamepad_disconnected.connect(self.process_gamepad_disconnected)
        self.gamepad.gamepad_connected.connect(self.process_gamepad_connected)
        self.activate_gamepad_index.pressed.connect(self.process_activate_gamepad_index)
        self.activate_gamepad_scan.pressed.connect(self.process_activate_gamepad_scan)
        self.activate_gamepad_index.setVisible(False)
        self.activate_gamepad_scan.setVisible(False)
        self.gamepad.start()

        if PYINSTALLER:
            icon1 = qtg.QIcon()
            icon1.addPixmap(qtg.QPixmap(sys.prefix + "./gamepad.png"), qtg.QIcon.Normal, qtg.QIcon.Off)
            self.activate_gamepad_index.setIcon(icon1)
            self.activate_gamepad_scan.setIcon(icon1)
            self.label_51.setPixmap(qtg.QPixmap(sys.prefix + "./xbox_gamepad.jpg"))

        # Setup Scan Options
        self.scan_start_button.pressed.connect(self.process_scan_start_button)
        self.scan_wait_for_motion_complete = ThreadWaitForMotionComplete("C")
        self.scan_wait_for_motion_complete.connection.reported_error_message.connect(self.error_mg.setText)
        self.scan_wait_for_motion_complete.motion_completed.connect(self.process_scan_point)
        self.index_wait_for_motion_complete = ThreadWaitForMotionComplete(["A", "B"])
        self.index_wait_for_motion_complete.connection.reported_error_message.connect(self.error_mg.setText)
        self.index_wait_for_motion_complete.motion_completed.connect(self.process_scan_point)
        self.scan_stop_button.pressed.connect(self.process_scan_stop_button)
        self.scan_pause_button.pressed.connect(self.process_scan_pause_button)
        self.scan_resume_button.pressed.connect(self.process_scan_resume_button)
        self.scan_point_index = 0
        self.scan_points = []
        self.scanning_active = False  # While scanning: True. Paused scan: False
        self.mode_scanning_active = False  # True when start scan is pressed until stop scan is pressed
        self.send_galil_cmd.pressed.connect(self.process_send_galil_cmd)
        self.slider_angle_correction_intensity.valueChanged.connect(
            lambda value: self.process_slider_angle_correction_intensity(value))
        self.slider_angle_correction_intensity.setValue(int(0.7 * self.slider_angle_correction_intensity.maximum()))

        # Setup Scan Axis Setup
        self.calculate_scan_scaling_factor.pressed.connect(self.process_calculate_scan_scaling_factor)
        self.apply_scan_axis_scaling_factor.pressed.connect(self.process_apply_scan_axis_scaling_factor)
        self.checkBox_reverseScanFeedback.clicked.connect(self.process_checkBox_reverseScanFeedback)
        self.checkBox_reverseScanMotor.clicked.connect(self.process_checkBox_reverseScanMotor)
        self.apply_scan_axis_error_limit.pressed.connect(self.process_apply_scan_axis_error_limit)
        self.scan_axis_current_limit_slider.valueChanged.connect(self.process_scan_axis_current_limit_slider_change)
        self.scan_axis_torque_control.edit.setText("3.00")  # Init current limit at 3A

        # Setup Index Axis Setup
        self.calculate_index_scaling_factor.pressed.connect(self.process_calculate_index_scaling_factor)
        self.apply_index_axis_scaling_factor.pressed.connect(self.process_apply_index_axis_scaling_factor)
        self.checkBox_reverseLeftFeedback.clicked.connect(self.process_checkBox_reverseLeftFeedback)
        self.checkBox_reverseRightFeedback.clicked.connect(self.process_checkBox_reverseRightFeedback)
        self.checkBox_reverseFollowerFeedback.clicked.connect(self.process_checkBox_reverseLeftFeedback)
        self.checkBox_reverseLeftMotor.clicked.connect(self.process_checkBox_reverseLeftMotor)
        self.checkBox_reverseRightMotor.clicked.connect(self.process_checkBox_reverseRightMotor)
        self.apply_index_axis_error_limits.pressed.connect(self.process_apply_index_axis_error_limits)
        self.index_axis_current_limit_slider.valueChanged.connect(self.process_index_axis_current_limit_slider_change)
        self.index_axis_torque_control.edit.setText("3.00")  # Init current limit at 3A

        self.clear_fault.pressed.connect(lambda: self.error_mg.setText(""))

        self.process_apply_scan_axis_scaling_factor()
        self.process_apply_scan_axis_error_limit()
        self.process_apply_index_axis_scaling_factor()
        self.process_apply_index_axis_error_limits()
        self.set_soft_limits.setChecked(True)

        self.running_average_delta_counts = 0
        # self.text_box.textChanged.connect(self.process_incoming_serial_data)

        # self.index_timer = qtc.QTimer()
        # self.index_timer.timeout.connect(self.get_index_axis_faults)
        self.serial_in_use = False
        self.serial_string = ""
        self.refresh_scan_faults.pressed.connect(self.process_refresh_scan_faults)
        self.refresh_index_faults.pressed.connect(self.process_refresh_index_faults)

        # self.refresh_scan_faults.pressed.connect(self.get_scan_axis_faults)
        self.waiting_for_scan_fault_data = False
        self.gathering_scan_fault_data = False
        self.scan_waiting_for_index_axis = False
        self.scan_ack_sent = False
        self.scan_faults = VaredanFaults(self.clear_scan_faults,
                                         [self.scan_fault_0,
                                          self.scan_fault_1,
                                          self.scan_fault_2,
                                          self.scan_fault_3,
                                          self.scan_fault_4,
                                          self.scan_fault_5,
                                          self.scan_fault_6,
                                          self.scan_fault_7,
                                          self.scan_fault_8,
                                          self.scan_fault_9,
                                          self.scan_fault_10,
                                          self.scan_fault_11,
                                          self.scan_fault_12,
                                          self.scan_fault_13,
                                          self.scan_fault_14,
                                          self.scan_fault_15,
                                          self.scan_fault_16
                                          ])
        # self.refresh_index_faults.pressed.connect(self.get_index_axis_faults)
        self.waiting_for_index_fault_data = False
        self.gathering_index_fault_data = False
        self.index_waiting_for_scan_axis = False
        self.index_ack_sent = False
        self.index_faults = VaredanFaults(self.clear_index_faults,
                                          [self.index_fault_0,
                                           self.index_fault_1,
                                           self.index_fault_2,
                                           self.index_fault_3,
                                           self.index_fault_4,
                                           self.index_fault_5,
                                           self.index_fault_6,
                                           self.index_fault_7,
                                           self.index_fault_8,
                                           self.index_fault_9,
                                           self.index_fault_10,
                                           self.index_fault_11,
                                           self.index_fault_12,
                                           self.index_fault_13,
                                           self.index_fault_14,
                                           self.index_fault_15,
                                           self.index_fault_32
                                           ])

        self.process_refresh_scan_faults()
        self.process_refresh_index_faults()
        self.ack_mc_faults.pressed.connect(self.process_ack_mc_faults)

    # Called when the user changes focus to see if any line edits have invalid input
    def focus_changed_checks(self):
        for i in range(len(self.myEdits)):
            self.myEdits[i].incomplete_check()

    #############################
    # Fault Processing Methods #
    #############################
    def process_ack_mc_faults(self):

        font = qtg.QFont()
        font.setBold(False)
        font.setWeight(50)
        if self.cb_software_estop.isChecked():
            self.cb_software_estop.setFont(font)
            self.cb_software_estop.setChecked(False)
            self.enable_gui_after_estop_fault()
            self.estop.setStyleSheet("background-color: light grey")
        if self.cb_hardware_estop.isChecked():
            self.cb_hardware_estop.setFont(font)
            self.cb_hardware_estop.setChecked(False)
            self.enable_gui_after_estop_fault()
            self.estop.setStyleSheet("background-color: light grey")
            # Change the hardware ESTOP, this will get enabled again if ESTOP is still pressed
            if self.hardware_estop_state:
                self.hardware_estop_state = False

        # Clear vega feedback faults as they will get enabled again automatically
        self.cb_left_fb_fault.setChecked(False)
        self.cb_left_fb_fault.setFont(font)
        self.cb_right_fb_fault.setChecked(False)
        self.cb_right_fb_fault.setFont(font)
        self.cb_scan_fb_fault.setChecked(False)
        self.cb_scan_fb_fault.setFont(font)
        self.cb_follower_fb_fault.setChecked(False)
        self.cb_follower_fb_fault.setFont(font)

        # Left position fault
        if self.cb_left_position_fault.isChecked():
            self.cb_left_position_fault.setChecked(False)
            self.cb_left_position_fault.setFont(font)
            self.enable_index_axis.setEnabled(True)

        # Right position fault
        if self.cb_right_position_fault.isChecked():
            self.cb_right_position_fault.setChecked(False)
            self.cb_right_position_fault.setFont(font)
            self.enable_index_axis.setEnabled(True)

        # Scan position fault
        if self.cb_scan_position_fault.isChecked():
            self.cb_scan_position_fault.setChecked(False)
            self.cb_scan_position_fault.setFont(font)
            self.enable_scan_axis.setEnabled(True)

        if self.cb_follower_position_fault.isChecked():
            self.cb_follower_position_fault.setChecked(False)
            self.cb_follower_position_fault.setFont(font)
            # Return jogging buttons to normal for index axis
            self.move_index_to_zero.setEnabled(True)
            self.move_index_to_position.setEnabled(True)
            self.toggle_move_type.setEnabled(True)
            self.jog_index_ccw.setEnabled(True)
            self.jog_index_cw.setEnabled(True)
            self.jog_index_fwd.setEnabled(True)
            self.jog_index_rev.setEnabled(True)
            self.enable_incremental_moves()

    def process_software_estop(self):
        self.gcmd('AB 1')
        self.estop.setStyleSheet("background-color: red")
        font = qtg.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.cb_software_estop.setFont(font)
        self.cb_software_estop.setChecked(True)
        self.disable_gui_from_estop_fault()

    def process_hardware_estop(self):
        if not self.hardware_estop_state:
            self.estop.setStyleSheet("background-color: red")
            font = qtg.QFont()
            font.setBold(True)
            font.setWeight(75)
            self.cb_hardware_estop.setFont(font)
            self.cb_hardware_estop.setChecked(True)
            self.disable_gui_from_estop_fault()
            self.hardware_estop_state = True

    def keyPressEvent(self, event):
        if event.key() == qtc.Qt.Key_Escape:
            self.process_software_estop()

    #############################
    # Scan Axis Related Methods #
    #############################

    def process_jog_left(self):
        speed = -int(self.scan_axis_speed_slider.value())
        self.scan_axis_state = -1
        self.gcmd('JG ,,' + str(speed))
        self.gcmd('BG C')

    def process_jog_right(self):
        speed = speed = int(self.scan_axis_speed_slider.value())
        self.scan_axis_state = 1
        self.gcmd('JG ,,' + str(speed))
        self.gcmd('BG C')

    def stop_scan_jog(self):
        self.gcmd('ST C')
        self.scan_axis_state = 0

    def process_set_scan_position_zero(self):
        self.gcmd('DP ,,0')

    def process_set_scan_position_to(self):
        new_position = self.scaling_scan_axis * float(self.set_scan_position_edit.text())
        self.gcmd('DP ,,' + str(new_position))

    def process_move_scan_to_zero(self):
        # Enter position tracking mode, set position absolute, speed, and begin movement
        self.gcmd('PT 0,0,1')
        self.gcmd('PA ,,0')

    def process_move_scan_to_position(self):
        self.gcmd('PT 0,0,1')
        new_position = self.scaling_scan_axis * float(self.move_scan_to_edit.text())
        if self.sign_toggled_scan_axis:
            new_position *= -1
        self.gcmd('PA ,,' + str(new_position))
        speed = int(self.scan_axis_speed_slider.value())
        self.gcmd('SP ,,' + str(speed))

    def process_set_soft_limits(self):
        # Check if the change was from impartial input from the user
        left = self.left_soft_limit_edit.text()
        right = self.right_soft_limit_edit.text()
        if left == "" or left == "-" or left == "." or left == "+":
            return
        if right == "" or right == "-" or right == "." or right == "+":
            return

        # Either the user has entered valid data or the state of the checkbox has been changed
        if self.set_soft_limits.isChecked():
            right = int(float(self.right_soft_limit_edit.text()) * self.scaling_scan_axis)
            left = int(float(self.left_soft_limit_edit.text()) * self.scaling_scan_axis)
            self.gcmd('FL ,,' + str(right))
            self.gcmd('BL ,,' + str(left))
        elif not self.set_soft_limits.isChecked():
            self.gcmd('FL ,,' + str(FL))
            self.gcmd('BL ,,' + str(BL))

    def process_scan_axis_speed_slider_change(self):
        # speed = int(self.scan_axis_speed_control.value() * 1000000)
        speed = self.scan_axis_speed_slider.value()
        if self.scan_axis_state:
            speed = speed * self.scan_axis_state
        if not int(float(self.gcmd('PTC=?'))):
            self.gcmd('JG ,,' + str(speed))
        else:
            self.gcmd('SP ,,' + str(speed))

    def process_enable_scan(self):
        # Check if motor is enabled_index; _MOx = 1 when disabled
        motor_c_status = not int(float(self.gcmd('MG _MOC')))
        feedback_fault_scan = self.vega_scan.report_fault()

        # Servo the motors if there is not an amplifier fault
        if not self.fault_scan.isChecked() and not feedback_fault_scan:
            # Motor is disabled
            if not motor_c_status:
                self.gcmd('SH C')
            else:
                self.stop_scan_jog()
                self.wait_for_scan_disable.start()
        # If the user clicks on the axis to enable it and there is an amplifier error
        else:
            self.stop_scan_jog()
            self.wait_for_scan_disable.start()

    def turn_off_scan_motor(self):
        self.gcmd('MOC')
        self.wait_for_scan_disable.stop()

    def process_scan_axis_sign_toggle(self):
        if not self.scan_axis_sign_toggle.isChecked():
            self.scan_axis_sign_toggle.setIcon(self.icon_plus)
            self.scan_axis_sign_toggle.setStyleSheet("background-color: light grey")
            self.sign_toggled_scan_axis = False
        else:
            self.scan_axis_sign_toggle.setIcon(self.icon_minus)
            self.scan_axis_sign_toggle.setStyleSheet("background-color: magenta")
            self.sign_toggled_scan_axis = True

        self.set_scan_position_edit.setText(str(float(self.set_scan_position_edit.text()) * -1))
        self.move_scan_to_edit.setText(str(float(self.move_scan_to_edit.text()) * -1))
        self.left_soft_limit_edit.setText(str(float(self.left_soft_limit_edit.text()) * -1))
        self.right_soft_limit_edit.setText(str(float(self.right_soft_limit_edit.text()) * -1))

    def process_activate_gamepad_scan(self):
        self.gamepad_enabled_for_scan.emit(True)
        if not self.activate_gamepad_scan.isVisible():
            self.activate_gamepad_scan.setVisible(True)
        elif self.activate_gamepad_scan.isChecked():
            factor = float(self.max_scan_gamepad_speed_edit.text()) / 3
            current_value = self.scan_axis_speed_control.slider.value()
            self.scan_axis_speed_control.slider.setValue(int(current_value / factor))
            self.enable_jogging_buttons_scan()
            self.gamepad_enabled_for_scan.emit(False)
            self.stop_scan_jog()
            self.activate_gamepad_scan.setStyleSheet("background-color: light grey")
        else:
            self.restore_scan_speed_sent.emit(
                self.scan_axis_speed_slider.value() / self.scan_axis_speed_slider.maximum())
            self.disable_jogging_buttons_scan()
            self.gamepad_enabled_for_scan.emit(True)
            self.activate_gamepad_scan.setStyleSheet("background-color: green")

    def process_checkBox_reverseScanFeedback(self):
        if self.checkBox_reverseScanFeedback.isChecked():
            self.gcmd('CE ,,2')
        else:
            self.gcmd('CE ,,0')

    def process_checkBox_reverseScanMotor(self):
        if self.checkBox_reverseScanMotor.isChecked():
            self.gcmd('MT ,,-1')
        else:
            self.gcmd('MT ,,1')

    def process_apply_scan_axis_error_limit(self):
        error_limit_inches = float(self.scan_axis_error_limit.text())
        error_limit_counts = int(error_limit_inches * self.scaling_scan_axis)
        self.gcmd('ER ,,' + str(error_limit_counts))
        self.scan_axis_error_limit.setStyleSheet("background-color: springgreen")

    def process_fault_scan(self):
        # Call method to start to gather data about the fault or lack of fault
        self.waiting_for_scan_fault_data = True
        self.clear_serial_string_for_scan()

        if self.fault_scan.isChecked():
            self.enable_scan_axis.setStyleSheet("background-color: red")
        else:
            self.enable_scan_axis.setStyleSheet("")

    # Clear the data saved from the serial connection in preparation for asking the amplifier the fault status
    def clear_serial_string_for_scan(self):
        # Disable the clear and refresh buttons to alert the user the work taking place
        self.clear_scan_faults.setEnabled(False)
        self.refresh_scan_faults.setEnabled(False)
        self.label_gathering_scan_fault_data.setHidden(False)
        # Check if the serial connection is free, and check if the scan axis has started to gather data
        if not self.serial_in_use and not self.gathering_scan_fault_data and self.waiting_for_scan_fault_data:
            self.serial_in_use = True
            self.gathering_scan_fault_data = True
            qtc.QTimer.singleShot(1000, self.clear_serial_string_for_scan)
            return
        # Assume that enough time has passed and you can now send an inquiry command about faults
        elif self.gathering_scan_fault_data and self.waiting_for_scan_fault_data and self.serial_in_use:
            # If the serial connection has not been switched, come back later because it takes time for the hardware
            if self.varedan_select.currentIndex() != 0:
                self.varedan_select.setCurrentIndex(0)  # TODO: added this back?
                qtc.QTimer.singleShot(100, self.clear_serial_string_for_scan)
                return
            if not self.scan_ack_sent:
                self.cmd_text.setText("A1")
                self.send_cmd.click()
                self.scan_ack_sent = True
                qtc.QTimer.singleShot(100, self.clear_serial_string_for_scan)
                return
            self.serial_string = ""
            self.cmd_text.setText("A")
            self.send_cmd.click()
            qtc.QTimer.singleShot(1000, self.get_data_scan)
        # Serial must be in use, try again later
        else:
            qtc.QTimer.singleShot(1000, self.clear_serial_string_for_scan)

    # Clear the data saved from the serial connection in preparation for asking the amplifier the fault status
    def clear_serial_string_for_index(self):
        # Disable the clear and refresh buttons to alert the user the work taking place
        self.clear_index_faults.setEnabled(False)
        self.refresh_index_faults.setEnabled(False)
        self.label_gathering_index_fault_data.setHidden(False)
        # Check if the serial connection is free, and check if the index axis has started to gather data
        if not self.serial_in_use and not self.gathering_index_fault_data and self.waiting_for_index_fault_data:
            self.serial_in_use = True
            self.gathering_index_fault_data = True
            qtc.QTimer.singleShot(1000, self.clear_serial_string_for_index)
            return
        elif self.gathering_index_fault_data and self.waiting_for_index_fault_data and self.serial_in_use:
            # If the serial connection has not been switched, come back later because it takes time for the hardware
            if self.varedan_select.currentIndex() != 1:
                self.varedan_select.setCurrentIndex(1)
                qtc.QTimer.singleShot(100, self.clear_serial_string_for_index)
                return
            if not self.index_ack_sent:
                self.cmd_text.setText("A1")
                self.send_cmd.click()
                self.index_ack_sent = True
                qtc.QTimer.singleShot(100, self.clear_serial_string_for_index)
                return

            self.serial_string = ""
            self.cmd_text.setText("A")
            self.send_cmd.click()
            qtc.QTimer.singleShot(1000, self.get_data_index)
        else:
            qtc.QTimer.singleShot(1000, self.clear_serial_string_for_index)

    def get_data_scan(self):
        # Assume that serial string only has data related to A call
        self.scan_faults.process_serial_string(self.serial_string)
        self.serial_in_use = False
        self.waiting_for_scan_fault_data = False
        self.gathering_scan_fault_data = False
        self.scan_ack_sent = False
        # Enable the clear and refresh buttons to alert the user the work is done
        self.clear_scan_faults.setEnabled(True)
        self.refresh_scan_faults.setEnabled(True)
        self.label_gathering_scan_fault_data.setHidden(True)

    def get_data_index(self):
        # Assume that serial string only has data related to A call
        self.index_faults.process_serial_string(self.serial_string)
        self.serial_in_use = False
        self.waiting_for_index_fault_data = False
        self.gathering_index_fault_data = False
        self.index_ack_sent = False
        # Enable the clear and refresh buttons to alert the user the work is done
        self.clear_index_faults.setEnabled(True)
        self.refresh_index_faults.setEnabled(True)
        self.label_gathering_index_fault_data.setHidden(True)

    def process_refresh_scan_faults(self):
        self.scan_faults.clear_faults()
        self.waiting_for_scan_fault_data = True
        self.clear_serial_string_for_scan()

    def process_refresh_index_faults(self):
        self.index_faults.clear_faults()
        self.waiting_for_index_fault_data = True
        self.clear_serial_string_for_index()

    def process_clear_screen(self):
        self.text_box.clear()

    # Updates the enable scan button to be green/light grey when there is a state change, also updates position error
    def update_scan_axis_status(self, data):
        feedback_fault_scan = int(float(data[1]))
        # If there is a fault the process_enable_scan method will take appropriate steps
        if self.fault_scan.isChecked():
            self.process_enable_scan()

        # Check if there is a vega card fault, make red, which supersedes making the button grey
        if feedback_fault_scan:
            self.cb_scan_fb_fault.setChecked(True)
            font = qtg.QFont()
            font.setBold(True)
            font.setWeight(75)
            self.cb_scan_fb_fault.setFont(font)

            if not "red" in self.enable_scan_axis.styleSheet():
                self.enable_scan_axis.setStyleSheet("background-color: red")
                self.enable_scan_axis_2.setStyleSheet("background-color: red")

        # Check if motor is off, set enable button to grey
        elif int(data[0]) & 32:
            if self.scan_axis_is_enabled:
                self.scan_axis_is_enabled = False
            # Make sure there is no amplifier error before clearing stylesheet
            if self.enable_scan_axis.styleSheet() and not self.fault_scan.isChecked():
                self.enable_scan_axis.setStyleSheet("")
                self.enable_scan_axis_2.setStyleSheet("")
        # Check if motor is on
        elif not int(data[0]) & 32:
            # Set the enabled variable if there are no VEGA card fault, and no amplifier fault
            if not self.scan_axis_is_enabled and not self.fault_scan.isChecked():
                self.scan_axis_is_enabled = True
            # Set green if no VEGA card fault, and no amplifier fault
            if not "green" in self.enable_scan_axis.styleSheet() and not self.fault_scan.isChecked():
                self.enable_scan_axis.setStyleSheet("background-color: green")
                self.enable_scan_axis_2.setStyleSheet("background-color: green")

        # Check if there is a position error
        if int(data[0]) & 64:
            if not self.scan_axis_error:
                self.label_scan_position_error.setStyleSheet("background-color: red")
                self.cb_scan_position_fault.setChecked(True)
                font = qtg.QFont()
                font.setBold(True)
                font.setWeight(75)
                self.cb_scan_position_fault.setFont(font)
                if not self.scan_axis_error:
                    self.scan_axis_error = True
                    self.enable_scan_axis.setEnabled(False)
        # Check if there is no position error
        elif not int(data[0]) & 64:
            if self.scan_axis_error:
                self.label_scan_position_error.setStyleSheet("background-color: black; color: rgb(0,255,0)")
                self.scan_axis_error = False

    def process_gamepad_scan_speed_updated(self, speed):
        throttled_speed = (float(self.max_scan_gamepad_speed_edit.text()) / 3) * speed
        self.scan_axis_speed_slider.setValue(abs(int(self.scan_axis_speed_slider.maximum() * throttled_speed)))

    #############################
    # Index Axis Related Methods #
    #############################

    # Differential speed to counter drift
    def process_index_axis_speed_slider_change(self):
        slider_value = self.index_axis_balance_slider.value()
        velocity = self.index_axis_speed_slider.value()
        velocity_a = float(self.gcmd('TVA'))
        velocity_b = float(self.gcmd('TVB'))

        # At times when using the gamepad the velocity of the slider bar is much less than the actual velocity
        # This results in a very slow deceleration, and a deceleration time that varies
        if velocity < abs(velocity_a) and self.index_axis_balance_slider.value() >= 0:
            velocity = abs(velocity_a)
        elif velocity < abs(velocity_b) and self.index_axis_balance_slider.value() < 0:
            velocity = abs(velocity_b)

        # Right Turn, right motor is slower
        if slider_value > 0:
            normalized_slider_max = slider_value / self.index_axis_balance_slider.maximum()
            jog_right = velocity * (1 - normalized_slider_max)
            jog_left = velocity

        elif slider_value < 0:
            normalized_slider_min = slider_value / self.index_axis_balance_slider.minimum()
            jog_left = velocity * (1 - normalized_slider_min)
            jog_right = velocity
        else:
            jog_left = velocity
            jog_right = velocity

        max_time = 0.35  # Seconds
        max_vel = self.index_axis_speed_slider.maximum()
        decel_accel_time = (1 - ((max_vel - velocity) / max_vel)) * max_time + 0.1

        # Set the acceleration and deceleration so both motors stop at the same time.
        ac_dc_left = jog_left / decel_accel_time
        ac_dc_right = jog_right / decel_accel_time

        # If the calculated ac_dc is low, then hardcode a value
        default_ac_dc = abs(self.scaling_left_axis * 10)
        if ac_dc_left < default_ac_dc:
            ac_dc_left = default_ac_dc
        if ac_dc_right < default_ac_dc:
            ac_dc_right = default_ac_dc

        if not self.incremental_move_active:
            self.gcmd('AC ' + str(ac_dc_left) + "," + str(ac_dc_right))
            self.gcmd('DC ' + str(ac_dc_left) + "," + str(ac_dc_right))

        self.gcmd('SP ' + str(jog_left) + "," + str(jog_right))

    def process_jog_index_fwd(self):
        # Only begin a jog motion if the axis are stationary
        if int(float(self.gcmd('MG _BGA'))) == 0 and int(float(self.gcmd('MG _BGB'))) == 0:
            self.brake_left.setEnabled(True)
            self.brake_right.setEnabled(True)
            self.process_index_axis_speed_slider_change()
            jog_left = -int(self.gcmd('JGA=?'))
            jog_right = int(self.gcmd('JGB=?'))
            self.gcmd('JG ' + str(jog_left) + "," + str(jog_right))
            self.gcmd('BG A,B')
            if self.inclinometer.isRunning():
                if self.is_x_active_sensor:
                    if self.orientation_state == "RIGHT":
                        self.invert_tilt_sensor.setChecked(True)
                    elif self.orientation_state == "LEFT":
                        self.invert_tilt_sensor.setChecked(False)
                else:
                    if self.orientation_state == "UP":
                        self.invert_tilt_sensor.setChecked(True)
                    elif self.orientation_state == "DOWN":
                        self.invert_tilt_sensor.setChecked(False)

    def process_jog_index_rev(self):
        # Only begin a jog motion if the axis are stationary
        if int(float(self.gcmd('MG _BGA'))) == 0 and int(float(self.gcmd('MG _BGB'))) == 0:
            self.brake_left.setEnabled(True)
            self.brake_right.setEnabled(True)
            self.process_index_axis_speed_slider_change()
            jog_left = int(self.gcmd('JGA=?'))
            jog_right = -int(self.gcmd('JGB=?'))
            self.gcmd('JG ' + str(jog_left) + "," + str(jog_right))
            self.gcmd('BG A,B')
            if self.inclinometer.isRunning():
                if self.is_x_active_sensor:
                    if self.orientation_state == "RIGHT":
                        self.invert_tilt_sensor.setChecked(False)
                    elif self.orientation_state == "LEFT":
                        self.invert_tilt_sensor.setChecked(True)
                else:
                    if self.orientation_state == "UP":
                        self.invert_tilt_sensor.setChecked(False)
                    elif self.orientation_state == "DOWN":
                        self.invert_tilt_sensor.setChecked(True)

    def stop_index_jog(self):
        self.brake_left.setEnabled(False)
        self.brake_right.setEnabled(False)
        if self.incremental_moves.isRunning():
            self.stop_inc_move()
        else:
            self.gcmd('ST A,B')
            self.gcmd('JG 0,0')

    def process_jog_index_cw(self):
        self.brake_left.setEnabled(True)
        self.brake_right.setEnabled(True)
        self.process_index_axis_speed_slider_change()
        jog_left = -int(self.gcmd('JGA=?'))
        jog_right = -int(self.gcmd('JGB=?'))
        self.gcmd('JG ' + str(jog_left) + "," + str(jog_right))
        self.gcmd('BG A,B')

    def process_jog_index_ccw(self):
        self.brake_left.setEnabled(True)
        self.brake_right.setEnabled(True)
        self.process_index_axis_speed_slider_change()
        jog_left = int(self.gcmd('JGA=?'))
        jog_right = int(self.gcmd('JGB=?'))
        self.gcmd('JG ' + str(jog_left) + "," + str(jog_right))
        self.gcmd('BG A,B')

    # Disable/Enable appropriate buttons and set state variables to enter jogging mode
    def enable_jogging_moves(self):
        self.stop_inc_move()  # Stop thread
        self.move_index_to_zero.setEnabled(False)
        self.move_index_to_position.setEnabled(False)
        self.jog_index_ccw.setEnabled(True)
        self.jog_index_cw.setEnabled(True)
        self.jog_index_fwd.setEnabled(True)
        self.jog_index_rev.setEnabled(True)
        # Brakes are false in jogging mode and only become active when movement is happening
        self.brake_left.setEnabled(False)
        self.brake_right.setEnabled(False)
        self.set_index_position_zero.setEnabled(True)
        self.set_index_position_to.setEnabled(True)

        # Set state variables
        self.mode_incremental_active = False
        self.mode_jogging_active = True

    # Disable/Enable appropriate buttons and set state variables to enter incremental mode
    def enable_incremental_moves(self):
        self.move_index_to_zero.setEnabled(True)
        self.move_index_to_position.setEnabled(True)
        self.jog_index_ccw.setEnabled(False)
        self.jog_index_cw.setEnabled(False)
        self.jog_index_fwd.setEnabled(False)
        self.jog_index_rev.setEnabled(False)
        self.brake_left.setEnabled(True)
        self.brake_right.setEnabled(True)
        self.set_index_position_zero.setEnabled(False)
        self.set_index_position_to.setEnabled(False)

        # Set state variables
        self.mode_incremental_active = True
        self.mode_jogging_active = False

        # Set the current index position as the target position
        self.follower_target = float(self.label_follower_position.text()) * self.scaling_follower_axis
        self.start_inc_move()

    # Switch between jogging and incremental movements
    def process_toggle_move_type(self):
        # Enter Jogging Mode
        if self.mode_incremental_active and not self.mode_jogging_active:
            self.enable_jogging_moves()
        # Enter Incremental Moves
        elif not self.mode_incremental_active and self.mode_jogging_active:
            self.enable_incremental_moves()
        else:
            self.toggle_move_type.setStyleSheet("background-color: red")

    def process_move_index_to_zero(self):
        # Enter position tracking mode
        self.gcmd('PT 1,1')
        # Set the target position
        self.follower_target = 0
        self.start_inc_move()

    def process_move_index_to_position(self):
        self.gcmd('PT 1,1')
        self.follower_target = float(self.move_index_to_edit.text()) * self.scaling_follower_axis
        if self.sign_toggled_index_axis:
            self.follower_target *= -1
        self.start_inc_move()

    # Thread to constantly update PT command for incremental move
    def start_inc_move(self):
        self.process_index_axis_speed_slider_change()
        self.incremental_moves.start()
        self.incremental_move_active = True
        self.incremental_move_in_position = False

    def process_set_index_position_zero(self):
        self.gcmd('DP 0,0')
        self.gcmd('DE 0')

    def process_fault_index(self):
        # Call method to start to gather data about the fault or lack of fault
        self.waiting_for_index_fault_data = True
        self.clear_serial_string_for_index()

        if self.fault_index.isChecked():
            self.enable_index_axis.setStyleSheet("background-color: red")
        else:
            self.enable_index_axis.setStyleSheet("")

    def process_set_index_position_to(self):
        new_position = self.scaling_left_axis * float(self.set_index_position_edit.text())
        follower_position = self.scaling_follower_axis * float(self.set_index_position_edit.text())
        if self.sign_toggled_index_axis:
            new_position *= -1
            follower_position *= -1
        self.gcmd('DP ' + str(new_position) + "," + str(-new_position))
        self.gcmd('DE ' + str(follower_position))

    def process_enable_index(self):
        motor_a_status = not int(float(self.gcmd('MG _MOA')))
        motor_b_status = not int(float(self.gcmd('MG _MOB')))
        feedback_fault_left = self.vega_left.report_fault()
        feedback_fault_right = self.vega_right.report_fault()
        feedback_fault_follower = self.vega_follower.report_fault()

        # Servo the motors if there is not an amplifier or VEGA fault
        if not self.fault_index.isChecked() and not feedback_fault_left and not feedback_fault_right and not feedback_fault_follower:
            # If both motors are not servoed then servo, otherwise turn off both motors because the amplifier cannot servo only one
            if not motor_a_status and not motor_b_status:
                self.gcmd('SH A,B')
            else:
                self.stop_index_jog()
                self.wait_for_index_disable.start()
        # If the user clicks on the axis to enable it and there is an error
        else:
            if self.incremental_move_active:
                self.stop_inc_move()
            self.stop_index_jog()
            self.wait_for_index_disable.start()

    def turn_off_index_motors(self):
        self.gcmd('MO A,B')
        self.wait_for_index_disable.stop()

    def update_index_axis_status(self, data):
        feedback_fault_left = int(float(data[2]))
        feedback_fault_right = int(float(data[3]))
        feedback_fault_follower = int(float(data[4]))

        # If there is a fault the process_enable_index method will take appropriate steps.
        if self.fault_index.isChecked():
            self.process_enable_index()

        # Check if there is a vega card fault, make red, which supersedes making the button grey
        if feedback_fault_right or feedback_fault_left or feedback_fault_follower:
            if not "red" in self.enable_index_axis.styleSheet():
                self.enable_index_axis.setStyleSheet("background-color: red")
                self.enable_index_axis_2.setStyleSheet("background-color: red")
            if feedback_fault_left:
                self.cb_left_fb_fault.setChecked(True)
                font = qtg.QFont()
                font.setBold(True)
                font.setWeight(75)
                self.cb_left_fb_fault.setFont(font)
            if feedback_fault_right:
                self.cb_right_fb_fault.setChecked(True)
                font = qtg.QFont()
                font.setBold(True)
                font.setWeight(75)
                self.cb_right_fb_fault.setFont(font)
            if feedback_fault_follower:
                self.cb_follower_fb_fault.setChecked(True)
                font = qtg.QFont()
                font.setBold(True)
                font.setWeight(75)
                self.cb_follower_fb_fault.setFont(font)

        # Check if motors are off or if motor status is not the same
        elif (int(data[0]) & 32 and int(data[1]) & 32) or (int(data[0]) & 32 != int(data[1]) & 32):
            if self.index_axis_is_enabled:
                self.index_axis_is_enabled = False
            if self.enable_index_axis.styleSheet() and not self.fault_index.isChecked():
                self.enable_index_axis.setStyleSheet("")
                self.enable_index_axis_2.setStyleSheet("")
        # Check if motors are on
        elif not int(data[0]) & 32 and not int(data[1]) & 32:
            if not self.index_axis_is_enabled and not self.fault_index.isChecked():
                self.index_axis_is_enabled = True
            if not "green" in self.enable_index_axis.styleSheet() and not self.fault_index.isChecked():
                self.enable_index_axis.setStyleSheet("background-color: green")
                self.enable_index_axis_2.setStyleSheet("background-color: green")

        # Check if there is a position error on the left axis
        if int(data[0]) & 64:
            if not self.index_left_axis_error:
                self.label_left_position_error.setStyleSheet("background-color: red")
                self.cb_left_position_fault.setChecked(True)
                font = qtg.QFont()
                font.setBold(True)
                font.setWeight(75)
                self.cb_left_position_fault.setFont(font)
                if not self.index_left_axis_error:
                    self.index_left_axis_error = True
                    self.enable_index_axis.setEnabled(False)
        elif not int(data[0]) & 64:
            if self.index_left_axis_error:
                self.label_left_position_error.setStyleSheet("background-color: black; color: rgb(0,255,0)")
                self.index_left_axis_error = False

        # Check if there is a position error on the right axis
        if int(data[1]) & 64:
            if not self.index_right_axis_error:
                self.label_right_position_error.setStyleSheet("background-color: red")
                self.cb_right_position_fault.setChecked(True)
                font = qtg.QFont()
                font.setBold(True)
                font.setWeight(75)
                self.cb_right_position_fault.setFont(font)
                if not self.index_right_axis_error:
                    self.index_right_axis_error = True
                    self.enable_index_axis.setEnabled(False)
        elif not int(data[1]) & 64:
            if self.index_right_axis_error:
                self.label_right_position_error.setStyleSheet("background-color: black; color: rgb(0,255,0)")
                self.index_right_axis_error = False

    def process_activate_gamepad_index(self):
        # First check if gamepad button is invisible then make it visible
        if not self.activate_gamepad_index.isVisible():
            self.activate_gamepad_index.setVisible(True)
        # If the gamepad button is checked then exit gamepad mode
        elif self.activate_gamepad_index.isChecked():
            factor = float(self.max_index_gamepad_speed_edit.text()) / 3
            current_value = self.index_axis_speed_control.slider.value()
            self.index_axis_speed_control.slider.setValue(int(current_value / factor))
            self.enable_jogging_moves()
            self.toggle_move_type.setEnabled(True)
            self.gamepad_enabled_for_index.emit(False)
            self.stop_index_jog()
            self.activate_gamepad_index.setStyleSheet("background-color: light grey")
        # Enter gamepad mode for index
        else:
            self.restore_index_speed_sent.emit(
                self.index_axis_speed_slider.value() / self.index_axis_speed_slider.maximum())
            # Enter jogging mode if not already in that mode
            self.enable_jogging_moves()
            self.disable_jogging_index_buttons_for_gamepad()
            self.toggle_move_type.setEnabled(False)
            self.gamepad_enabled_for_index.emit(True)
            self.activate_gamepad_index.setStyleSheet("background-color: green")

    def process_index_axis_sign_toggle(self):
        if not self.index_axis_sign_toggle.isChecked():
            self.index_axis_sign_toggle.setIcon(self.icon_plus)
            self.index_axis_sign_toggle.setStyleSheet("background-color: light grey")
            self.sign_toggled_index_axis = False
        else:
            self.index_axis_sign_toggle.setIcon(self.icon_minus)
            self.index_axis_sign_toggle.setStyleSheet("background-color: magenta")
            self.sign_toggled_index_axis = True

        self.set_index_position_edit.setText(str(float(self.set_index_position_edit.text()) * -1))
        self.move_index_to_edit.setText(str(float(self.move_index_to_edit.text()) * -1))

    def process_left_brake(self):
        self.left_brake_engaged = True
        # When using incremental moves, the ST command will cancel the PA mode previously setup
        if not self.scanning_active and not self.incremental_move_active:
            # Set the deceleration very high so the braking happens quickly
            self.gcmd('DC 50000000')
            self.gcmd('ST A')

    # Called by brake status thread, waits for motion to decelerate when brake click is faster than deceleration time
    def process_left_brake_status(self, data):
        in_motion = int(float(data[0]))
        if not in_motion:
            # Stop the thread which was reporting the motion status
            self.left_brake_status.stop()
            # Simulate a second click of the brake now that motion has stopped.
            self.brake_left.click()

    def process_right_brake(self):
        self.right_brake_engaged = True
        # When using incremental moves, the ST command will cancel the PA mode previously setup
        if not self.scanning_active and not self.incremental_move_active:
            # Set the deceleration very high so the braking happens quickly
            self.gcmd('DC , 50000000')
            self.gcmd('ST B')

    def process_right_brake_status(self, data):
        in_motion = int(float(data[0]))
        if not in_motion:
            self.right_brake_status.stop()
            self.brake_right.click()

    # Called after brake button is released
    def process_brake_release(self):
        if not self.scanning_active and not self.incremental_move_active:
            # Left brake button released
            if self.sender().objectName() == "brake_left":
                # If axis is not in motion then command motion again
                if not int(float(self.gcmd('MG _BGA'))):
                    self.gcmd('BG A')
                    self.left_brake_engaged = False
                # The brake button is released after a quick press, but the axis is still decelerating. Start a thread
                # to monitor the brake status and then issue a move command once the axis has come to a full stop
                else:
                    self.left_brake_status.start()

            elif self.sender().objectName() == "brake_right":
                if not int(float(self.gcmd('MG _BGB'))):
                    self.gcmd('BG B')
                    self.right_brake_engaged = False
                else:

                    self.right_brake_status.start()
            else:
                print("ERROR: No sender of brake")
        # Incremental move is active as stand alone or as part of a scanning index move
        else:
            if self.sender().objectName() == "brake_left":
                self.left_brake_engaged = False
            if self.sender().objectName() == "brake_right":
                self.right_brake_engaged = False

    # Start collecting data for auto angle
    def process_activateAngle(self):
        self.activateAngle.setEnabled(False)
        self.activateAngle.setChecked(True)
        self.activateAngle.setStyleSheet("background-color: green;\nfont: 10pt \"MS Shell Dlg 2\";")
        self.deactivateAngle.setEnabled(True)
        # Call the commanded angle each time because the voltage setpoint can be different despite commanding the same angle
        self.process_new_commanded_angle(self.commanded_angle.text())
        self.auto_angle_is_active = True

    def process_deactivateAngle(self):
        self.activateAngle.setEnabled(True)
        self.activateAngle.setChecked(False)
        self.activateAngle.setStyleSheet("background-color: light grey;\nfont: 10pt \"MS Shell Dlg 2\";")
        self.deactivateAngle.setEnabled(False)
        self.index_axis_balance_slider.setValue(0)
        self.voltageCommand.setText("(V)")
        self.auto_angle_is_active = False

    def process_new_commanded_angle(self, deg):
        if deg != "" and deg != "-":
            deg = float(deg)
            if self.orientation_state == "UP" or self.orientation_state == "RIGHT":
                deg *= -1
                voltage = int(1000 * (deg + 20.522) / 8.222)
            else:
                voltage = int(1000 * (1.5 * deg / 20 + 2.5))
            self.angle_setpoint_slider.setValue(voltage)

    def update_setpoint(self, sp):
        self.pid.setpoint = sp / 1000
        self.voltageSetpoint.setText(str('{:.2f}'.format(self.pid.setpoint)))

    # voltages[0] = y sensor
    def process_inclinometer_data(self, voltages):
        if self.invert_y.isChecked():
            y_raw = round(float(voltages[0]), 2)
            y_raw = 5 - y_raw
            voltages[0] = str(y_raw)

        if self.invert_x.isChecked():
            x_raw = round(float(voltages[1]), 2)
            x_raw = 5 - x_raw
            voltages[1] = str(x_raw)

        if is_active(voltages[0]) and not is_active(voltages[1]):
            voltage = voltages[0]
        elif is_active(voltages[1]) and not is_active(voltages[0]):
            voltage = voltages[1]
        else:
            voltage = 2.5

        N = 5
        # Calculate moving average of raw voltage output of tilt sensor
        self.running_average_vfbk -= self.running_average_vfbk / N
        self.running_average_vfbk += round(float(voltage) / N, 4)
        self.voltageActual.setText(str('{:.2f}'.format(self.running_average_vfbk)))
        self.measured_angle.setText(voltage_to_degree(str(self.running_average_vfbk), self.orientation_state))
        self.angle_readout.update_value(
            float((voltage_to_degree(str(self.running_average_vfbk), self.orientation_state))))

        if self.auto_angle_is_active:
            # Voltage coming in is a list 0: INC  Y, 1: INC X
            # Select the active sensor for the user
            if is_active(voltages[0]) and not is_active(voltages[1]):
                voltage = voltages[0]
                self.is_x_active_sensor = False
                if self.radio_x_active.isChecked() or not self.radio_y_active.isChecked():
                    self.radio_x_active.setChecked(False)
                    self.radio_y_active.setChecked(True)
            elif is_active(voltages[1]) and not is_active(voltages[0]):
                voltage = voltages[1]
                self.is_x_active_sensor = True
                if not self.radio_x_active.isChecked() or self.radio_y_active.isChecked():
                    self.radio_x_active.setChecked(True)
                    self.radio_y_active.setChecked(False)
            else:
                voltage = 2.5
                if DEBUG:
                    print("ERROR: No Active Angle Configuration")

            voltage = float(voltage)
            newSliderValue = self.pid(voltage)
            if self.invert_tilt_sensor.isChecked():
                newSliderValue = 5 - newSliderValue
            # Balance axis has values of -50 to +50, convert value
            self.index_axis_balance_slider.setValue(int((newSliderValue - 2.5) * 20))

            N = 5
            # Calculate moving average of command voltage for display purposes
            self.running_average_vcmd -= self.running_average_vcmd / N
            self.running_average_vcmd += round(float(newSliderValue) / N, 4)
            self.voltageCommand.setText(str('{:.2f}'.format(self.running_average_vcmd)))

    def process_checkBox_reverseRightFeedback(self):
        if self.checkBox_reverseRightFeedback.isChecked():
            self.gcmd('CE ,2')
        else:
            self.gcmd('CE ,0')

    def process_checkBox_reverseLeftFeedback(self):
        if self.checkBox_reverseLeftFeedback.isChecked() and self.checkBox_reverseFollowerFeedback.isChecked():
            self.gcmd('CE 10')
        elif self.checkBox_reverseLeftFeedback.isChecked() and not self.checkBox_reverseFollowerFeedback.isChecked():
            self.gcmd('CE 2')
        elif not self.checkBox_reverseLeftFeedback.isChecked() and self.checkBox_reverseFollowerFeedback.isChecked():
            self.gcmd('CE 8')
        else:
            self.gcmd('CE 0')

    def process_checkBox_reverseLeftMotor(self):
        if self.checkBox_reverseLeftMotor.isChecked():
            self.gcmd('MT -1')
        else:
            self.gcmd('MT 1')

    def process_checkBox_reverseRightMotor(self):
        if self.checkBox_reverseRightMotor.isChecked():
            self.gcmd('MT ,-1')
        else:
            self.gcmd('MT ,1')

    def process_apply_index_axis_error_limits(self):
        left_error_limit_inches = float(self.left_axis_error_limit.text())
        left_error_limit_counts = abs(int(left_error_limit_inches * self.scaling_left_axis))

        right_error_limit_inches = float(self.right_axis_error_limit.text())
        right_error_limit_counts = abs(int(right_error_limit_inches * self.scaling_right_axis))

        follower_error_limit_inches = float(self.follower_axis_error_limit.text())
        self.allowable_following_error = abs(follower_error_limit_inches * self.scaling_follower_axis)

        self.gcmd('ER ' + str(left_error_limit_counts) + ',' + str(right_error_limit_counts))
        self.left_axis_error_limit.setStyleSheet("background-color: springgreen")
        self.right_axis_error_limit.setStyleSheet("background-color: springgreen")
        self.follower_axis_error_limit.setStyleSheet("background-color: springgreen")

    def process_gamepad_index_speed_updated(self, speed):
        throttled_speed = (float(self.max_index_gamepad_speed_edit.text()) / 3) * speed
        self.index_axis_speed_slider.setValue(abs(int(self.index_axis_speed_slider.maximum() * throttled_speed)))

    ################################
    # Scan Options Related Methods #
    ################################

    def process_scan_start_button(self):
        # If the gamepad is active, calling the following will deactivate it
        if self.activate_gamepad_index.isChecked():
            self.activate_gamepad_index.click()
        if self.activate_gamepad_scan.isChecked():
            self.activate_gamepad_scan.click()
        # Enter incremental_moves before starting the scanning sequence
        self.enable_incremental_moves()
        self.prepare_gui_for_scanning()
        self.create_scan_points()
        self.mode_scanning_active = True
        self.scanning_active = True
        self.scan_resume_button.setEnabled(False)
        self.scan_start_button.setEnabled(False)
        self.scan_stop_button.setEnabled(True)
        self.scan_pause_button.setEnabled(True)
        self.process_scan_point()

    def process_scan_stop_button(self):
        self.restore_gui_from_scanning()
        self.enable_jogging_moves()
        self.gcmd('ST A,B,C')
        self.scan_wait_for_motion_complete.stop()
        self.index_wait_for_motion_complete.stop()
        self.scan_point_index = 0
        self.scanning_active = False
        self.mode_scanning_active = False
        self.scan_points.clear()
        self.process_deactivateAngle()
        self.scan_pause_button.setEnabled(False)
        self.scan_resume_button.setEnabled(False)
        self.scan_stop_button.setEnabled(False)
        self.scan_start_button.setEnabled(True)

    def process_scan_pause_button(self):
        self.gcmd('ST A,B,C')
        self.restore_gui_from_scanning()
        self.scan_options_index_start.setEnabled(False)
        self.scan_options_index_size.setEnabled(False)
        self.enable_incremental_moves()
        self.scanning_active = False
        self.process_deactivateAngle()
        self.scan_pause_button.setEnabled(False)
        self.scan_resume_button.setEnabled(True)

    def process_scan_resume_button(self):
        # If the gamepad is active, calling the following will deactivate it
        if self.activate_gamepad_index.isChecked():
            self.activate_gamepad_index.click()
        if self.activate_gamepad_scan.isChecked():
            self.activate_gamepad_scan.click()
        # If the user switched to jogging moves, switch back to incremental moves
        self.enable_incremental_moves()
        self.prepare_gui_for_scanning()
        self.create_scan_points()
        self.scanning_active = True
        self.scan_pause_button.setEnabled(True)
        self.scan_resume_button.setEnabled(False)
        self.process_scan_point()

    def process_scan_point(self):
        scan_in_position = False
        index_in_position = False

        if self.scanning_active:
            # Check if done with all scan points:
            if self.scan_point_index >= len(self.scan_points):
                self.process_scan_stop_button()
                return

            # Check if Scan axis is in position
            position = float(self.label_scan_position.text())
            if abs(self.scan_points[self.scan_point_index][0] - position) <= 0.03:
                if DEBUG:
                    print("Scan axis is in position")
                scan_in_position = True

            elif self.scan_points[self.scan_point_index][0] != float(self.label_scan_position.text()):
                if DEBUG:
                    print("Issued Scan Move")
                if self.auto_incline_check_box.isChecked():
                    self.process_deactivateAngle()
                self.scan_points[self.scan_point_index].append(time.time())
                self.execute_scan_line(self.scan_points[self.scan_point_index][0],
                                       float(self.scan_options_scan_edit.text()))
                self.scan_wait_for_motion_complete.start()
                return
            # Check if Index axis is in position
            position = float(self.label_follower_position.text())
            if abs(self.scan_points[self.scan_point_index][1] - position) <= 0.03:
                if DEBUG:
                    print("Index axis is in position")
                index_in_position = True
            elif self.scan_points[self.scan_point_index][1] != float(self.label_follower_position.text()):
                overshoot_flag = False
                # Check the direction of required scan movement
                if self.scan_points[self.scan_point_index][1] < float(self.label_follower_position.text()):
                    # Position overshoot with positive indexing
                    if (float(self.scan_options_index_stop.text()) - float(self.scan_options_index_start.text())) > 0:
                        overshoot_flag = True
                elif self.scan_points[self.scan_point_index][1] > float(self.label_follower_position.text()):
                    if (float(self.scan_options_index_stop.text()) - float(self.scan_options_index_start.text())) < 0:
                        overshoot_flag = True

                if DEBUG:
                    print("Issued Index Move")
                if self.auto_incline_check_box.isChecked():
                    # Determine if the invert angle gui_input is needed

                    # Index start is less than index end
                    if float(self.scan_options_index_start.text()) <= float(self.scan_options_index_stop.text()):
                        if self.orientation_state == "DOWN":
                            # Driving reverse
                            if self.sign_toggled_index_axis:
                                self.invert_tilt_sensor.setChecked(True)
                            # Driving forward
                            else:
                                self.invert_tilt_sensor.setChecked(False)
                        elif self.orientation_state == "RIGHT":
                            # Driving reverse
                            if self.sign_toggled_index_axis:
                                self.invert_tilt_sensor.setChecked(False)
                            # Driving forward
                            else:
                                self.invert_tilt_sensor.setChecked(True)
                        elif self.orientation_state == "LEFT":
                            # Driving reverse
                            if self.sign_toggled_index_axis:
                                self.invert_tilt_sensor.setChecked(True)
                            # Driving forward
                            else:
                                self.invert_tilt_sensor.setChecked(False)
                        elif self.orientation_state == "UP":
                            # Driving reverse
                            if self.sign_toggled_index_axis:
                                self.invert_tilt_sensor.setChecked(False)
                            # Driving forward
                            else:
                                self.invert_tilt_sensor.setChecked(True)

                    # Index start is greater than index end
                    elif float(self.scan_options_index_start.text()) > float(self.scan_options_index_stop.text()):
                        if self.orientation_state == "DOWN":
                            # Driving reverse
                            if self.sign_toggled_index_axis:
                                self.invert_tilt_sensor.setChecked(False)
                            # Driving forward
                            else:
                                self.invert_tilt_sensor.setChecked(True)
                        elif self.orientation_state == "RIGHT":
                            # Driving reverse
                            if self.sign_toggled_index_axis:
                                self.invert_tilt_sensor.setChecked(True)
                            # Driving forward
                            else:
                                self.invert_tilt_sensor.setChecked(False)
                        elif self.orientation_state == "LEFT":
                            # Driving reverse
                            if self.sign_toggled_index_axis:
                                self.invert_tilt_sensor.setChecked(False)
                            # Driving forward
                            else:
                                self.invert_tilt_sensor.setChecked(True)
                        elif self.orientation_state == "UP":
                            # Driving reverse
                            if self.sign_toggled_index_axis:
                                self.invert_tilt_sensor.setChecked(True)
                            # Driving forward
                            else:
                                self.invert_tilt_sensor.setChecked(False)

                    if overshoot_flag:
                        self.invert_tilt_sensor.setChecked(not self.invert_tilt_sensor.isChecked())
                    self.process_activateAngle()
                self.scan_points[self.scan_point_index].append(time.time())
                self.execute_index_line(self.scan_points[self.scan_point_index][1],
                                        float(self.scan_options_index_edit.text()))
                self.index_wait_for_motion_complete.start()
                return

            if scan_in_position and index_in_position:
                self.scan_point_index += 1
                self.process_scan_point()

    def execute_scan_line(self, new_position, new_speed):
        self.move_scan_to_edit.setText(str(new_position))
        self.scan_axis_speed_edit.setText(str(new_speed))
        self.process_move_scan_to_position()

        # Update the GUI with time remaining for the scan
        remaining_time_sec = 0
        for i in range(self.scan_point_index, len(self.scan_points) - 1):
            remaining_time_sec += self.scan_points[i][3]
        self.scan_time_remaining_edit.setText(str(int(remaining_time_sec / 60)))

    def execute_index_line(self, new_position, new_speed):
        self.move_index_to_edit.setText(str(new_position))
        self.index_axis_speed_edit.setText(str(new_speed))
        self.process_move_index_to_position()

    def create_scan_points(self):
        scan_start = float(self.scan_options_scan_start.text())
        scan_stop = float(self.scan_options_scan_stop.text())
        index_start = float(self.scan_options_index_start.text())
        index_size = float(self.scan_options_index_size.text())
        index_stop = float(self.scan_options_index_stop.text())

        # Definitions:
        #   OUT = Scan outwards from scan start to scan end
        #   IN = Scan inwards from scan end to scan start
        #   INDEX = move of one index_unit

        # Example Scan Point:
        #                       [scan position, index position, impending move type: OUT, IN, INDEX

        # Defined sequence of the repeat unit used to create the scan point list
        uni_move_sequence = ["OUT", "IN", "INDEX"]
        bi_move_sequence = ["OUT", "INDEX_0", "IN", "INDEX_1"]
        seq_index = 0

        # Check if index size is compatible
        if (index_stop - index_start) % index_size:
            print("\"Index Size\" should be divisible by \"Index Stop\" - \"Index Start\"")
            return
        # Confirm index size was entered as positive
        if index_size < 0:
            print("\"Index Size\" must be positive")
            return

        # Set the index unit to be positive or negative
        if (index_stop - index_start) >= 0:
            index_unit = index_size
        else:
            index_unit = - index_size

        counter = 0
        # Check if previous scan points have been processed
        if self.scan_point_index:
            last_realized = self.scan_points[self.scan_point_index - 1]
            index_position = last_realized[1]

            # Clear the scan point list and start new
            self.scan_points.clear()
            self.scan_point_index = 0

            # Make the new first data point, assume the user has changed the scanning parameters
            # UNI-DIRECTIONAL
            if self.uni_radio.isChecked() and not self.bi_radio.isChecked():
                seq_index = uni_move_sequence.index(last_realized[2])
                if last_realized[2] == "OUT":
                    self.scan_points.append([scan_start, index_position, "OUT"])
                elif last_realized[2] == "IN":
                    self.scan_points.append([scan_stop, index_position, "IN"])
                elif last_realized[2] == "INDEX":
                    self.scan_points.append([scan_start, index_position, "INDEX"])
                    index_position += index_unit
                seq_index = (seq_index + 1) % len(uni_move_sequence)
            # BI-DIRECTIONAL
            elif not self.uni_radio.isChecked() and self.bi_radio.isChecked():
                seq_index = bi_move_sequence.index(last_realized[2])
                if last_realized[2] == "OUT":
                    self.scan_points.append([scan_start, index_position, "OUT"])
                elif last_realized[2] == "INDEX_0":
                    self.scan_points.append([scan_stop, index_position, "INDEX_0"])
                    index_position += index_unit
                elif last_realized[2] == "IN":
                    self.scan_points.append([scan_stop, index_position, "IN"])
                elif last_realized[2] == "INDEX_1":
                    self.scan_points.append([scan_start, index_position, "INDEX_1"])
                    index_position += index_unit
                seq_index = (seq_index + 1) % len(bi_move_sequence)
        # No previous scan points, initialize loop variables from scratch
        else:
            seq_index = 1
            index_position = index_start
            # Create the first scan point, which is always "OUT" and then enter a loop
            self.scan_points.append([scan_start, index_position, "OUT"])

        # Create scan points for UNI-DIRECTIONAL scan
        if self.uni_radio.isChecked() and not self.bi_radio.isChecked():

            # UNI-DIRECTIONAL ends at "Scan Start" and index position of "Index Stop", at seq_index == 2 the previous
            # move was the last
            while seq_index != 2 or self.scan_points[counter][1] != index_stop:
                if uni_move_sequence[seq_index] == "OUT":
                    self.scan_points.append([scan_start, index_position, "OUT"])
                elif uni_move_sequence[seq_index] == "IN":
                    self.scan_points.append([scan_stop, index_position, "IN"])
                elif uni_move_sequence[seq_index] == "INDEX":
                    self.scan_points.append([scan_start, index_position, "INDEX"])
                    index_position += index_unit

                # The sequence index cannot exceed 2
                seq_index = (seq_index + 1) % 3
                counter += 1

        # Create scan points for BI-DIRECTIONAL scan
        elif not self.uni_radio.isChecked() and self.bi_radio.isChecked():
            # BI-DIRECTIONAL ends at "Scan Stop" and "Index Stop"
            while self.scan_points[counter][0] != scan_stop or self.scan_points[counter][1] != index_stop:
                if bi_move_sequence[seq_index] == "OUT":
                    self.scan_points.append([scan_start, index_position, "OUT"])
                elif bi_move_sequence[seq_index] == "INDEX_0":
                    self.scan_points.append([scan_stop, index_position, "INDEX_0"])
                    index_position += index_unit
                elif bi_move_sequence[seq_index] == "IN":
                    self.scan_points.append([scan_stop, index_position, "IN"])
                elif bi_move_sequence[seq_index] == "INDEX_1":
                    self.scan_points.append([scan_start, index_position, "INDEX_1"])
                    index_position += index_unit

                # The sequence index cannot exceed 3
                seq_index = (seq_index + 1) % 4
                counter += 1

        # Gather acceleration and speed in counts to calculate time for each move
        ac_index = float(self.gcmd('MG _ACA'))  # Assume A (left) and B (right) axis are the same acceleration
        ac_scan = float(self.gcmd('MG _ACC'))
        speed_index = abs(float(self.scan_options_index_edit.text()) * self.scaling_left_axis)
        speed_scan = abs(float(self.scan_options_scan_edit.text()) * self.scaling_scan_axis)

        for i in range(len(self.scan_points)):
            # If it there is an index move calculate total index movement
            if "INDEX" in self.scan_points[i][2]:
                if (i + 1) < len(self.scan_points):
                    # Get next index move
                    total_distance = abs(
                        abs(self.scan_points[i + 1][1] - self.scan_points[i][1]) * self.scaling_left_axis)
                    time_accel = speed_index / ac_index
                    time_accel_decel = 2 * time_accel
                    dist_accel_decel = time_accel * speed_index
                    dist_while_slewing = total_distance - dist_accel_decel
                    time_slewing = dist_while_slewing / speed_index
                    self.scan_points[i].append(round(time_accel_decel + time_slewing, 4))
            # Calculate the scan movement
            else:
                if (i + 1) < len(self.scan_points):
                    total_distance = abs(
                        abs(self.scan_points[i + 1][0] - self.scan_points[i][0]) * self.scaling_scan_axis)
                    time_accel = speed_scan / ac_scan
                    time_accel_decel = 2 * time_accel
                    dist_accel_decel = time_accel * speed_scan
                    dist_while_slewing = total_distance - dist_accel_decel
                    time_slewing = dist_while_slewing / speed_scan
                    self.scan_points[i].append(round(time_accel_decel + time_slewing, 4))

    def disable_gui_from_estop_fault(self):
        self.prepare_gui_for_scanning()
        self.scan_start_button.setEnabled(False)
        self.enable_scan_axis.setEnabled(False)
        self.enable_index_axis.setEnabled(False)

    def enable_gui_after_estop_fault(self):
        self.restore_gui_from_scanning()
        self.scan_start_button.setEnabled(True)
        self.enable_scan_axis.setEnabled(True)
        self.enable_index_axis.setEnabled(True)

    def prepare_gui_for_scanning(self):
        self.set_scan_position_to.setEnabled(False)
        self.set_scan_position_zero.setEnabled(False)
        self.set_scan_position_zero_2.setEnabled(False)
        self.jog_left.setEnabled(False)
        self.jog_left_2.setEnabled(False)
        self.jog_right.setEnabled(False)
        self.jog_right_2.setEnabled(False)
        self.move_scan_to_zero.setEnabled(False)
        self.move_scan_to_position.setEnabled(False)
        self.activate_gamepad_scan.setEnabled(False)
        self.activate_gamepad_index.setEnabled(False)
        self.set_soft_limits.setEnabled(False)
        self.scan_axis_speed_control.disable()

        self.set_index_position_to.setEnabled(False)
        self.set_index_position_zero.setEnabled(False)
        self.set_index_position_zero_2.setEnabled(False)
        self.jog_index_fwd.setEnabled(False)
        self.jog_index_fwd_2.setEnabled(False)
        self.jog_index_rev.setEnabled(False)
        self.jog_index_rev_2.setEnabled(False)
        self.move_index_to_zero.setEnabled(False)
        self.move_index_to_position.setEnabled(False)
        self.index_axis_speed_control.disable()
        self.index_axis_balance_control.disable()
        self.move_index_to_zero.setEnabled(False)
        self.move_index_to_position.setEnabled(False)
        self.toggle_move_type.setEnabled(False)
        self.jog_index_ccw.setEnabled(False)
        self.jog_index_cw.setEnabled(False)
        self.center_balance_slider.setEnabled(False)

        self.scan_options_scan_start.setEnabled(False)
        self.scan_options_scan_stop.setEnabled(False)
        self.scan_options_index_start.setEnabled(False)
        self.scan_options_index_size.setEnabled(False)
        self.scan_options_index_stop.setEnabled(False)
        self.scan_options_scan_speed_control.disable()
        self.scan_options_index_speed_control.disable()
        self.auto_incline_check_box.setEnabled(False)
        self.uni_radio.setEnabled(False)
        self.bi_radio.setEnabled(False)

        self.brake_left.setEnabled(True)
        self.brake_right.setEnabled(True)

        self.activateAngle.setEnabled(False)
        self.deactivateAngle.setEnabled(False)

    def restore_gui_from_scanning(self):
        self.set_scan_position_to.setEnabled(True)
        self.set_scan_position_zero.setEnabled(True)
        self.set_scan_position_zero_2.setEnabled(True)
        self.jog_left.setEnabled(True)
        self.jog_left_2.setEnabled(True)
        self.jog_right.setEnabled(True)
        self.jog_right_2.setEnabled(True)
        self.move_scan_to_zero.setEnabled(True)
        self.move_scan_to_position.setEnabled(True)
        self.activate_gamepad_scan.setEnabled(True)
        self.activate_gamepad_index.setEnabled(True)
        self.set_soft_limits.setEnabled(True)
        self.scan_axis_speed_control.enable()

        self.set_index_position_to.setEnabled(True)
        self.set_index_position_zero.setEnabled(True)
        self.set_index_position_zero_2.setEnabled(True)
        self.jog_index_fwd.setEnabled(True)
        self.jog_index_fwd_2.setEnabled(True)
        self.jog_index_rev.setEnabled(True)
        self.jog_index_rev_2.setEnabled(True)
        self.move_index_to_zero.setEnabled(True)
        self.move_index_to_position.setEnabled(True)
        self.activate_gamepad_index.setEnabled(True)
        self.index_axis_speed_control.enable()
        self.index_axis_balance_control.enable()
        self.move_index_to_zero.setEnabled(True)
        self.move_index_to_position.setEnabled(True)
        self.toggle_move_type.setEnabled(True)
        self.jog_index_ccw.setEnabled(True)
        self.jog_index_cw.setEnabled(True)
        self.center_balance_slider.setEnabled(True)

        self.scan_options_scan_start.setEnabled(True)
        self.scan_options_scan_stop.setEnabled(True)
        self.scan_options_index_start.setEnabled(True)
        self.scan_options_index_size.setEnabled(True)
        self.scan_options_index_stop.setEnabled(True)
        self.scan_options_scan_speed_control.enable()
        self.scan_options_index_speed_control.enable()
        self.auto_incline_check_box.setEnabled(True)
        self.uni_radio.setEnabled(True)
        self.bi_radio.setEnabled(True)

        self.activateAngle.setEnabled(True)
        self.deactivateAngle.setEnabled(True)

    def process_slider_angle_correction_intensity(self, value):
        # Get value of slider
        percentage = value / self.slider_angle_correction_intensity.maximum()
        low_value = round(2.5 - 2.5 * percentage, 3)
        high_vale = round(2.5 + 2.5 * percentage, 3)
        self.pid.output_limits = (low_value, high_vale)

    ###################################
    # Scan Axis Setup Related Methods #
    ###################################

    # After a new counts/inch has been calculated adjust the speed slider bar
    def adjust_speed_slider_maximum(self, slider_w_edit: SliderWithEdit, max_count_speed):
        max_inch_speed = slider_w_edit.max_allowed
        # Make a single step 0.01 inch/second change
        slider_w_edit.slider.setSingleStep(int(max_count_speed / 100))
        # Make a page step be 10% of the max allowable speed
        result = 0.1 * max_inch_speed * max_count_speed
        slider_w_edit.slider.setPageStep(int(result))
        # Set Maximum speed
        slider_w_edit.slider.setMaximum(int(max_count_speed * max_inch_speed))
        slider_w_edit.update_conversion_factor()
        slider_w_edit.edit.setText(str(max_inch_speed * 0.25))

    def process_calculate_scan_scaling_factor(self):
        counts = float(self.scan_axis_counts.text())
        distance = float(self.scan_distance_jogged.text())
        self.scan_axis_scaling_factor.setStyleSheet("")
        if distance != 0:
            result = round(counts / distance, 2)  # Units: Counts/Inch
            self.scan_axis_scaling_factor.setText(str(result))

    def process_apply_scan_axis_scaling_factor(self):
        # Adjust the maximum speed for the scan axis slider
        sf = float(self.scan_axis_scaling_factor.text())
        if sf != 0:
            self.adjust_speed_slider_maximum(self.scan_axis_speed_control, abs(sf))
            self.scaling_scan_axis = sf
            self.scan_axis_scaling_factor.setStyleSheet("background-color: springgreen")
            self.process_apply_scan_axis_error_limit()
            # Calculate the acceleration and deceleration by multiplying the scaling factor by 12 resulting in 0.25" slow down time at 3"/second
            acdc = abs(sf * 12)
            self.gcmd('AC ,,' + str(acdc))
            self.gcmd('DC ,,' + str(acdc))
            # Increase the Soft Limit Deceleration to prevent overshoot at high speeds
            self.gcmd('SD ,,' + str(acdc * 10))
            # Set the new soft limits
            self.process_set_soft_limits()

    def process_scan_axis_current_limit_slider_change(self):
        tl = self.scan_axis_current_limit_edit.text()
        self.gcmd('TL ,,' + tl)

    ####################################
    # Index Axis Setup Related Methods #
    ####################################

    def process_calculate_index_scaling_factor(self):
        counts_left = float(self.left_motor_counts.text())
        distance = float(self.index_distance_jogged.text())

        self.index_axis_left_scaling_factor.setStyleSheet("")
        self.index_axis_right_scaling_factor.setStyleSheet("")
        self.follower_scaling_factor.setStyleSheet("")

        if distance != 0:
            result = round(counts_left / distance, 2)  # Units: Counts/Inch
            self.index_axis_left_scaling_factor.setText(str(result))

        counts_right = float(self.right_motor_counts.text())
        distance = float(self.index_distance_jogged.text())
        if distance != 0:
            result = round(counts_right / distance, 2)  # Units: Counts/Inch
            self.index_axis_right_scaling_factor.setText(str(result))

        counts_follower = float(self.follower_counts.text())
        distance = float(self.index_distance_jogged.text())
        if distance != 0:
            result = round(counts_follower / distance, 2)  # Units: Counts/Inch
            self.follower_scaling_factor.setText(str(result))

    def process_apply_index_axis_scaling_factor(self):
        # Adjust the maximum speed for the index axis slider, 3"/sec is hardcoded maximum
        result_left = float(self.index_axis_left_scaling_factor.text())
        if result_left != 0:
            self.adjust_speed_slider_maximum(self.index_axis_speed_control, abs(result_left))
            self.scaling_left_axis = result_left
            self.index_axis_left_scaling_factor.setStyleSheet("background-color: springgreen")
            self.process_apply_index_axis_error_limits()
        result_right = float(self.index_axis_right_scaling_factor.text())
        if result_right != 0:
            self.scaling_right_axis = result_right
            self.index_axis_right_scaling_factor.setStyleSheet("background-color: springgreen")
            self.process_apply_index_axis_error_limits()
        result_follower = float(self.follower_scaling_factor.text())
        if result_follower != 0:
            self.scaling_follower_axis = result_follower
            self.follower_scaling_factor.setStyleSheet("background-color: springgreen")
            self.process_apply_index_axis_error_limits()

    def process_index_axis_current_limit_slider_change(self):
        tl = self.index_axis_current_limit_edit.text()
        self.gcmd('TL ' + tl + ',' + tl)

    ###################################################################################################

    def process_pid(self):
        if self.kp_edit.text() == '':
            self.kp_edit.setText(str(self.pid.Kp))
            self.ki_edit.setText(str(self.pid.Ki))
            self.kd_edit.setText(str(self.pid.Kd))
        else:
            self.pid.Kp = float(self.kp_edit.text())
            self.pid.Ki = float(self.ki_edit.text())
            self.pid.Kd = float(self.kd_edit.text())

    def process_gamepad_connected(self):
        self.activate_gamepad_index.setVisible(True)
        self.activate_gamepad_scan.setVisible(True)

    def process_gamepad_disconnected(self):
        self.gamepad_enabled_for_index.emit(False)  # TODO: make variable for gamepad enabled_index for index and scan
        self.gamepad_enabled_for_scan.emit(False)
        self.stop_index_jog()
        self.stop_scan_jog()
        self.activate_gamepad_index.setVisible(False)
        self.activate_gamepad_index.setChecked(False)
        self.activate_gamepad_scan.setVisible(False)
        self.activate_gamepad_scan.setChecked(False)
        self.enable_jogging_buttons_index()
        self.enable_jogging_buttons_scan()
        self.activate_gamepad_index.setStyleSheet("background-color: light grey")
        self.activate_gamepad_scan.setStyleSheet("background-color: light grey")

    def gcmd(self, cmd):
        try:
            result = self.connection.gcmd(cmd)
            return result
        except gclib.GclibError as e:
            if str(e) == 'question mark returned by controller':
                self.error_mg.setText("DMC Error: " + self.connection.g.GCommand('TC1'))
            else:
                print('Unexpected GclibError:', e)

    def process_start_program(self):
        self.gcmd('XQ #I_SCOM,0')
        self.serialThread.start()
        self.start_program.setEnabled(False)
        self.stop_program.setEnabled(True)

    def process_stop_program(self):
        self.gcmd('HX #I_SCOM, 0')
        self.serialThread.stop()
        self.start_program.setEnabled(True)

    def display_serial_data(self, key):
        self.text_box.appendPlainText(key)
        self.serial_string += key

    def process_send_cmd(self):
        cmd_str = "MG {P2} \"" + self.cmd_text.text() + "\"{^13}{N}"
        self.gcmd(cmd_str)

    def process_varedan_select(self):
        if self.varedan_select.currentIndex() == 1:
            self.gcmd('CB 1')
        elif self.varedan_select.currentIndex() == 0:
            self.gcmd('SB 1')

    # TODO: change this name to disable all movement buttons
    def disable_jogging_index_buttons_for_gamepad(self):
        self.jog_index_cw.setEnabled(False)
        self.jog_index_ccw.setEnabled(False)
        self.jog_index_fwd.setEnabled(False)
        self.jog_index_rev.setEnabled(False)
        # self.brake_left.setEnabled(False)
        # self.brake_right.setEnabled(False)
        self.move_index_to_position.setEnabled(False)
        self.move_index_to_zero.setEnabled(False)

    # When exiting from gamepad control this method forces the user to jogging mode
    def enable_jogging_buttons_index(self):
        self.jog_index_cw.setEnabled(True)
        self.jog_index_ccw.setEnabled(True)
        self.jog_index_fwd.setEnabled(True)
        self.jog_index_rev.setEnabled(True)
        self.brake_left.setEnabled(False)
        self.brake_right.setEnabled(False)
        self.move_index_to_position.setEnabled(False)
        self.move_index_to_zero.setEnabled(False)

    def enable_jogging_buttons_scan(self):
        self.jog_left.setEnabled(True)
        self.jog_right.setEnabled(True)
        self.move_scan_to_zero.setEnabled(True)
        self.move_scan_to_position.setEnabled(True)

    def disable_jogging_buttons_scan(self):
        self.jog_left.setEnabled(False)
        self.jog_right.setEnabled(False)
        self.move_scan_to_zero.setEnabled(False)
        self.move_scan_to_position.setEnabled(False)

    def stop_inc_move(self):
        self.incremental_moves.stop()
        self.gcmd('ST A,B')  # This needed to stop "slewing" of the A and B so next scan move can happen
        self.incremental_move_active = False

    # Calculates new PT position needed for incremental move
    def update_error(self, data):
        encoder_a = float(data[0])
        follower = float(data[1])
        encoder_b = float(data[2])
        ratio = abs(
            self.scaling_left_axis / self.scaling_follower_axis)  # Motor encoder counts divided by follower encoder counts
        # Calculate motor encoder counts to get to follower set point
        delta_counts = ((self.follower_target - follower) * ratio)

        # Check if the follower is within 50 counts of the target
        # If counts of follower are off the target by set amount, issue a new move if user isn't pressing the brakes
        if abs(delta_counts) > 50 and not self.left_brake_engaged and not self.right_brake_engaged:
            self.gcmd('PA ' + str(encoder_a + delta_counts) + "," + str(encoder_b - delta_counts))
        # If left brake, get current position and command axis to stay in that position.
        elif abs(delta_counts) > 50 and self.left_brake_engaged and not self.right_brake_engaged:
            self.gcmd('PA ' + self.gcmd('TPA') + "," + str(encoder_b - delta_counts))
        # If right brake, get current position and command axis to stay in that position.
        elif abs(delta_counts) > 50 and not self.left_brake_engaged and self.right_brake_engaged:
            self.gcmd('PA ' + str(encoder_a + delta_counts) + "," + self.gcmd('TPB'))
        # If both brakes are engaged
        elif abs(delta_counts) > 50 and self.left_brake_engaged and self.right_brake_engaged:
            self.gcmd('PA ' + self.gcmd('TPA') + "," + self.gcmd('TPB'))
        # If there is acceptable error, stop the thread if scanning
        else:
            # When in scan mode, the auto angle won't work unless I stop the incremental moves
            if self.scanning_active:
                self.stop_inc_move()
            self.incremental_move_in_position = True

    # Tool angle adjustment calculation, Note: Pins down is the correct orientation for the tilt sensor
    def auto_angle_adjustment(self, voltages):
        # Voltage coming in is a list 0: INC  Y, 1: INC X
        # Select the active sensor for the user
        if is_active(voltages[0]) and not is_active(voltages[1]):
            voltage = voltages[0]
            self.is_x_active_sensor = False
            if self.radio_x_active.isChecked() or not self.radio_y_active.isChecked():
                self.radio_x_active.setChecked(False)
                self.radio_y_active.setChecked(True)
        elif is_active(voltages[1]) and not is_active(voltages[0]):
            voltage = voltages[1]
            self.is_x_active_sensor = True
            if not self.radio_x_active.isChecked() or self.radio_y_active.isChecked():
                self.radio_x_active.setChecked(True)
                self.radio_y_active.setChecked(False)
        else:
            voltage = 2.5

        voltage = float(voltage)
        newSliderValue = self.pid(voltage)
        if self.invert_tilt_sensor.isChecked():
            newSliderValue = 5 - newSliderValue
        # Balance axis has values of -50 to +50, convert value
        self.index_axis_balance_slider.setValue(int((newSliderValue - 2.5) * 20))

        N = 5
        # Calculate moving average of command voltage for display purposes
        self.running_average_vcmd -= self.running_average_vcmd / N
        self.running_average_vcmd += round(float(newSliderValue) / N, 4)
        self.voltageCommand.setText(str('{:.2f}'.format(self.running_average_vcmd)))

    def closeEvent(self, event):
        self.process_software_estop()
        self.gcmd('RS')
        self.connection.close()

    # Update the labels on the GUI for the position, velocity, error, current
    def update_data(self, data):
        # Calculate GUI update data for the scan axis
        scan_position = round(float(data["scan pos"][0]) / self.scaling_scan_axis, 2)
        velocity_scan = round(float(data["scan vel"][0]) / self.scaling_scan_axis, 2)
        scan_position_error = round(float(data["scan pos err"][0]) / self.scaling_scan_axis, 2)

        # Check if the user has pressed the + - toggle button below the scan enable button
        if self.sign_toggled_scan_axis:
            scan_position *= -1
            velocity_scan *= -1
            scan_position_error *= -1

        self.label_scan_position.setText(str('{:.2f}'.format(scan_position)))
        self.label_velocity_scan.setText(str('{:.2f}'.format(velocity_scan)))
        self.label_scan_position_error.setText(
            str('{:.2f}'.format((scan_position_error / float(self.scan_axis_error_limit.text())) * 100)))

        # Calculate GUI update data for the index axis
        left_position = round(float(data["left pos"][0]) / self.scaling_left_axis, 2)
        right_position = round(float(data["right pos"][0]) / self.scaling_right_axis, 2)
        follower_position = round(float(data["follower pos"][0]) / self.scaling_follower_axis, 2)
        velocity_left = round(float(data["left vel"][0]) / self.scaling_left_axis, 2)
        velocity_right = round(float(data["right vel"][0]) / self.scaling_right_axis, 2)
        left_position_error = round(float(data["left pos err"][0]) / self.scaling_left_axis, 2)
        right_position_error = round(float(data["right pos err"][0]) / self.scaling_right_axis, 2)

        # Check if the user has pressed the + - toggle button below the index enable button
        if self.sign_toggled_index_axis:
            left_position *= -1
            right_position *= -1
            follower_position *= -1
            velocity_left *= -1
            velocity_right *= -1
            left_position_error *= -1
            right_position_error *= -1

        self.label_left_position.setText(str('{:.2f}'.format(left_position)))
        self.label_right_position.setText(str('{:.2f}'.format(right_position)))
        self.label_follower_position.setText(str('{:.2f}'.format(follower_position)))
        self.label_velocity_left.setText(str('{:.2f}'.format(velocity_left)))
        self.label_velocity_right.setText(str('{:.2f}'.format(velocity_right)))
        self.label_left_position_error.setText(
            str('{:.2f}'.format((left_position_error / float(self.left_axis_error_limit.text())) * 100)))
        self.label_right_position_error.setText(
            str('{:.2f}'.format((right_position_error / float(self.right_axis_error_limit.text())) * 100)))

        self.fault_index.setChecked(not int(round(float(data["index fault"][0]))))
        self.fault_scan.setChecked(not int(round(float(data["scan fault"][0]))))
        self.scan_axis_counts.setText(str(round(float(data["scan pos"][0]))))
        self.left_motor_counts.setText(str(round(float(data["left pos"][0]))))
        self.right_motor_counts.setText(str(round(float(data["right pos"][0]))))
        self.follower_counts.setText(str(round(float(data["follower pos"][0]))))

        if self.invert_y.isChecked():
            y_converted = round(float(data["inc y"][0]), 2)
            y_converted = 5 - y_converted
            data["inc y"][0] = str(y_converted)

        if self.invert_x.isChecked():
            x_converted = round(float(data["inc x"][0]), 2)
            x_converted = 5 - x_converted
            data["inc x"][0] = str(x_converted)

        self.inc_x.setText(str('{:.2f}'.format(round(float(data["inc x"][0]), 2))))
        self.inc_y.setText(str('{:.2f}'.format(round(float(data["inc y"][0]), 2))))

        if not int(float(data["estop"][0])):
            self.process_hardware_estop()

        # Change the background of the follower position if it is off as compared to the allowable error
        if abs((abs(float(data["follower pos"][0])) - abs(self.follower_target))) > self.allowable_following_error:
            # Check for scanning or perturbed system following completed incremental move
            if (self.scanning_active and not self.incremental_move_active) or (
                    self.incremental_move_active and self.incremental_move_in_position):
                saved_style = self.label_follower_position.styleSheet()
                updated_style_sheet = saved_style + ";\nbackground-color: red"
                self.label_follower_position.setStyleSheet(updated_style_sheet)
                # If scanning, pause the scan
                if self.scanning_active and not self.incremental_move_active:
                    self.process_scan_pause_button()
                # If incremental moves are active and tool has gotten to position but has since been moved.
                elif self.incremental_move_active and self.incremental_move_in_position:
                    self.stop_inc_move()
                    self.process_toggle_move_type()
                # Disable all jogging buttons for index axis so user has to acknowledge faults
                self.move_index_to_zero.setEnabled(False)
                self.move_index_to_position.setEnabled(False)
                self.toggle_move_type.setEnabled(False)
                self.jog_index_ccw.setEnabled(False)
                self.jog_index_cw.setEnabled(False)
                self.jog_index_fwd.setEnabled(False)
                self.jog_index_rev.setEnabled(False)
                font = qtg.QFont()
                font.setBold(True)
                font.setWeight(75)
                self.cb_follower_position_fault.setChecked(True)
                self.cb_follower_position_fault.setFont(font)
        else:
            saved_style = self.label_follower_position.styleSheet()
            updated_style_sheet = saved_style.replace(";\nbackground-color: red", "")
            self.label_follower_position.setStyleSheet(updated_style_sheet)

        N = 5
        # Calculate moving average
        self.left_mtr_cur_avg -= self.left_mtr_cur_avg / N
        self.left_mtr_cur_avg += round(float(data["left mtr cur"][0]) / N, 8)

        self.right_mtr_cur_avg -= self.right_mtr_cur_avg / N
        self.right_mtr_cur_avg += round(float(data["right mtr cur"][0]) / N, 8)

        self.scan_mtr_cur_avg -= self.scan_mtr_cur_avg / N
        self.scan_mtr_cur_avg += round(float(data["scan mtr cur"][0]) / N, 8)

        # Update current on GUI
        self.label_left_motor_current.setText(str('{:.2f}'.format(self.left_mtr_cur_avg)))
        self.label_right_motor_current.setText(str('{:.2f}'.format(self.right_mtr_cur_avg)))
        self.label_scan_motor_current.setText(str('{:.2f}'.format(self.scan_mtr_cur_avg)))

        # Update the current bars on the GUI
        pixmap = qtg.QPixmap(qtc.QSize(self.scan_current_bar_width, self.scan_current_bar_height))
        painter = qtg.QPainter(pixmap)
        pixmap.fill(qtc.Qt.black)
        width = self.scan_current_bar_width
        height = self.scan_current_bar_height
        painter.fillRect(width, height, -width, -abs(int(((self.scan_mtr_cur_avg / 2) * height))), qtc.Qt.red)
        painter.end()
        self.scan_current_bar.setPixmap(pixmap)

        pixmap = qtg.QPixmap(qtc.QSize(self.left_current_bar_width, self.left_current_bar_height))
        painter = qtg.QPainter(pixmap)
        pixmap.fill(qtc.Qt.black)
        width = self.left_current_bar_width
        height = self.left_current_bar_height
        painter.fillRect(width, height, -width, -abs(int(((self.left_mtr_cur_avg / 2) * height))), qtc.Qt.red)
        painter.end()
        self.left_current_bar.setPixmap(pixmap)

        pixmap = qtg.QPixmap(qtc.QSize(self.right_current_bar_width, self.right_current_bar_height))
        painter = qtg.QPainter(pixmap)
        pixmap.fill(qtc.Qt.black)
        width = self.right_current_bar_width
        height = self.right_current_bar_height
        painter.fillRect(width, height, -width, -abs(int(((self.right_mtr_cur_avg / 2) * height))), qtc.Qt.red)
        painter.end()
        self.right_current_bar.setPixmap(pixmap)

        # Update an arrow which represents the tool orientation
        if is_active(data["inc x"][0]) and is_sat_min(data["inc y"][0]):
            if PYINSTALLER:
                self.tool_orientation.setPixmap(qtg.QPixmap(sys.prefix + "./right-arrow.ico"))
            else:
                self.tool_orientation.setPixmap(qtg.QPixmap("Icons/right-arrow.ico"))
            self.orientation_state = "RIGHT"
            self.angle_readout.set_start_scale_angle(270)
            self.angle_readout.set_scala_main_count(6)
            self.angle_readout.set_MinValue(-15)
            self.angle_readout.set_MaxValue(15)
            self.angle_readout.set_enable_Needle_Polygon(True)
        elif is_active(data["inc x"][0]) and is_sat_max(data["inc y"][0]):
            if PYINSTALLER:
                self.tool_orientation.setPixmap(qtg.QPixmap(sys.prefix + "./left-arrow.ico"))
            else:
                self.tool_orientation.setPixmap(qtg.QPixmap("Icons/left-arrow.ico"))
            self.orientation_state = "LEFT"
            self.angle_readout.set_start_scale_angle(90)
            self.angle_readout.set_scala_main_count(10)
            self.angle_readout.set_MinValue(-25)
            self.angle_readout.set_MaxValue(25)
            self.angle_readout.set_enable_Needle_Polygon(True)
        elif is_active(data["inc y"][0]) and is_sat_max(data["inc x"][0]):
            if PYINSTALLER:
                self.tool_orientation.setPixmap(qtg.QPixmap(sys.prefix + "./up-arrow.ico"))
            else:
                self.tool_orientation.setPixmap(qtg.QPixmap("Icons/up-arrow.ico"))
            self.orientation_state = "UP"
            self.angle_readout.set_start_scale_angle(180)
            self.angle_readout.set_scala_main_count(6)
            self.angle_readout.set_MinValue(-15)
            self.angle_readout.set_MaxValue(15)
            self.angle_readout.set_enable_Needle_Polygon(True)
        elif is_active(data["inc y"][0]) and is_sat_min(data["inc x"][0]):
            if PYINSTALLER:
                self.tool_orientation.setPixmap(qtg.QPixmap(sys.prefix + "./down-arrow.ico"))
            else:
                self.tool_orientation.setPixmap(qtg.QPixmap("Icons/down-arrow.ico"))
            self.orientation_state = "DOWN"
            self.angle_readout.set_start_scale_angle(0)
            self.angle_readout.set_scala_main_count(10)
            self.angle_readout.set_MinValue(-25)
            self.angle_readout.set_MaxValue(25)
            self.angle_readout.set_enable_Needle_Polygon(True)
        elif is_sat_max(data["inc x"][0]) and is_sat_min(data["inc y"][0]):
            if PYINSTALLER:
                self.tool_orientation.setPixmap(qtg.QPixmap(sys.prefix + "./up-right-arrow.ico"))
            else:
                self.tool_orientation.setPixmap(qtg.QPixmap("Icons/up-right-arrow.ico"))
            self.angle_readout.set_enable_Needle_Polygon(False)
            # Check if the auto angle routine is running and turn it off
            if self.inclinometer.isRunning():
                self.process_deactivateAngle()
        elif is_sat_max(data["inc x"][0]) and is_sat_max(data["inc y"][0]):
            if PYINSTALLER:
                self.tool_orientation.setPixmap(qtg.QPixmap(sys.prefix + "./up-left-arrow.ico"))
            else:
                self.tool_orientation.setPixmap(qtg.QPixmap("Icons/up-left-arrow.ico"))
            self.angle_readout.set_enable_Needle_Polygon(False)
            # Check if the auto angle routine is running and turn it off
            if self.inclinometer.isRunning():
                self.process_deactivateAngle()
        elif is_sat_min(data["inc x"][0]) and is_sat_max(data["inc y"][0]):
            if PYINSTALLER:
                self.tool_orientation.setPixmap(qtg.QPixmap(sys.prefix + "./down-left-arrow.ico"))
            else:
                self.tool_orientation.setPixmap(qtg.QPixmap("Icons/down-left-arrow.ico"))
            self.angle_readout.set_enable_Needle_Polygon(False)
            # Check if the auto angle routine is running and turn it off
            if self.inclinometer.isRunning():
                self.process_deactivateAngle()
        elif is_sat_min(data["inc x"][0]) and is_sat_min(data["inc y"][0]):
            if PYINSTALLER:
                self.tool_orientation.setPixmap(qtg.QPixmap(sys.prefix + "./down-right-arrow.ico"))
            else:
                self.tool_orientation.setPixmap(qtg.QPixmap("Icons/down-right-arrow.ico"))
            self.angle_readout.set_enable_Needle_Polygon(False)
            # Check if the auto angle routine is running and turn it off
            if self.inclinometer.isRunning():
                self.process_deactivateAngle()
        else:
            self.tool_orientation.setPixmap(qtg.QPixmap(""))
            self.tool_orientation.setText("   BAD\n INPUT")

        # Check if the soft limits have been exceeded
        if self.set_soft_limits.isChecked():
            left = self.left_soft_limit_edit.text()
            right = self.right_soft_limit_edit.text()
            if left != "" and left != "-" and left != ".":
                if float(self.label_scan_position.text()) <= float(self.left_soft_limit_edit.text()):
                    self.label_31.setStyleSheet("background-color: red")
                else:
                    self.label_31.setStyleSheet("background-color: light grey")
            if right != "" and right != "-" and right != ".":
                if float(self.label_scan_position.text()) >= float(self.right_soft_limit_edit.text()):
                    self.label_30.setStyleSheet("background-color: red")
                else:
                    self.label_30.setStyleSheet("background-color: light grey")
        else:
            self.label_30.setStyleSheet("background-color: light grey")
            self.label_31.setStyleSheet("background-color: light grey")

    def process_send_galil_cmd(self):
        result = self.gcmd(self.cmd_text_edit.text())
        self.response_text_edit.setText(result)


# Thread to gather information to update the GUI with position, velocity, error, and motor current
class ThreadUpdate(qtc.QThread):
    data_ready = qtc.pyqtSignal(dict)

    def __init__(self, thread_name=""):
        super(ThreadUpdate, self).__init__()
        self.is_running = False
        self.thread_name = thread_name
        self.connection = Galil_Widget()
        self.data_packet = {
            "left pos": ['N/A', 'MG _TPA'],
            "right pos": ['N/A', 'MG _TPB'],
            "follower pos": ['N/A', 'MG _TDA'],
            "scan pos": ['N/A', 'MG _TPC'],
            "left vel": ['N/A', 'MG _TVA'],
            "right vel": ['N/A', 'MG _TVB'],
            "scan vel": ['N/A', 'MG _TVC'],
            "left pos err": ['N/A', 'MG _TEA'],
            "right pos err": ['N/A', 'MG _TEB'],
            "scan pos err": ['N/A', 'MG _TEC'],
            "left mtr cur": ['N/A', 'MG _TTA'],
            "right mtr cur": ['N/A', 'MG _TTB'],
            "scan mtr cur": ['N/A', 'MG _TTC'],
            "scan fault": ['N/A', 'MG @IN[1]'],
            "index fault": ['N/A', 'MG @IN[2]'],
            "inc x": ['N/A', 'MG @AN[2]'],
            "inc y": ['N/A', 'MG @AN[1]'],
            "estop": ['N/A', 'MG _AB']
        }

    def run(self):
        # if self.connection.connection_is_opened:
        self.is_running = True
        while self.is_running:
            time.sleep(0.01)
            for key in self.data_packet:
                self.data_packet[key][0] = self.connection.gcmd(self.data_packet[key][1])
            self.data_ready.emit(self.data_packet)

    def stop(self):
        self.is_running = False
        print("Stopping Thread:", self.thread_name)
        self.exit()


def convert_buffer_data(data: list):
    # Convert to characters
    for i in range(len(data)):
        if data[i] > 0:
            data[i] = chr(round(float(data[i])) >> 4 * 6)
        else:
            print("######################## Bad Data ######################################")
            # This could cause a problem if the bad data is also at this location
            data[i] = data[i - 1]

    # Remove NULL characters from list if they are present
    if data.count('\x00'):
        data.remove('\x00')

    # Remove the first CR and NL characters
    if data.count('\r'):
        data.remove('\r')
    if data.count('\n'):
        data.remove('\n')

    # Return a string of the result
    return ''.join(data)


# Notes: When I set my while loop to False, isRunning() always reports false, and self.is_running toggles
# When I change my while loop to True, isRunning() always reports True and the loop is running, self.is_running toggles
# When I set my while loop to self.is_running, both toggle appropriately
class ThreadSerial(qtc.QThread):
    reported_serial_data = qtc.pyqtSignal(str)

    def __init__(self, parent=None):
        super(ThreadSerial, self).__init__(parent)
        self.is_running = False
        self.connection = Galil_Widget()

    def run(self):
        # if self.connection.connection_is_opened:
        self.is_running = True
        while self.is_running:
            time.sleep(0.2)
            if self.buffer_has_data():
                # Get head and tail pointers
                head = int(float(self.connection.gcmd('MG head')))
                tail = int(float(self.connection.gcmd('MG tail')))
                buffer_size = int(float(self.connection.gcmd('MG bfsize')))
                # Get the python list equivalent of the array
                # If tail is > head, then the data overlaps index 0
                if tail > head:
                    data_list = self.connection.g.GArrayUpload('buffer', tail, (buffer_size - 1))
                    data_list.extend(self.connection.g.GArrayUpload('buffer', 0, head - 1))
                    self.reported_serial_data.emit(convert_buffer_data(data_list))
                else:
                    data_list = self.connection.g.GArrayUpload('buffer', tail, head - 1)
                    self.reported_serial_data.emit(convert_buffer_data(data_list))
                self.connection.gcmd('tail = ' + str(head))
                self.connection.gcmd('is_empty = True')

    # Thread for serial connection with LA 415 via AUX port on DMC 4040
    def buffer_has_data(self):
        # List the variables created in the DMC-4040
        variables = self.connection.gcmd('LV')
        # Check data set ready variable
        data_ready_flag = int(float(self.connection.gcmd('MG dsr')))
        if 'is_empty' in variables:
            # Buffer is not empty
            if int(float(self.connection.gcmd('MG is_empty'))) == 0 and data_ready_flag:
                return True
            # Buffer is empty
            elif int(float(self.connection.gcmd('MG is_empty'))) == 1:
                return False
        # Variable 'is_empty' is not present, program not loaded on DMC 4040
        else:
            return False

    def stop(self):
        self.is_running = False
        self.exit()


class ThreadDataFetch(qtc.QThread):
    received_data = qtc.pyqtSignal(list)
    refresh_wait = 0.01

    def __init__(self, commands, thread_name=""):
        super(ThreadDataFetch, self).__init__()
        self.is_running = False
        self.thread_name = thread_name
        self.connection = Galil_Widget()
        self.cmd_list = []
        for i in range(len(commands)):
            self.cmd_list.append(commands[i])

    def run(self):
        # if self.connection.connection_is_opened:
        self.is_running = True
        data = []
        while self.is_running:
            data.clear()
            time.sleep(self.refresh_wait)
            for i in range(len(self.cmd_list)):
                data.append(self.connection.gcmd(self.cmd_list[i]))
            self.received_data.emit(data)

    def stop(self):
        self.is_running = False
        self.quit()
        self.wait()  # Needed to wait for the thread to finish running
        if DEBUG:
            print("Thread", self.thread_name, "Terminated by sender:", self.senderSignalIndex())
        self.connection.close()


class ThreadWaitForMotionComplete(qtc.QThread):
    motion_completed = qtc.pyqtSignal()

    def __init__(self, axis=None):
        super(ThreadWaitForMotionComplete, self).__init__()
        self.is_running = False
        self.connection = Galil_Widget()
        self.axis = axis
        self.sleep_time = 0.01
        # time.sleep(0.1)

    def run(self):
        # if self.connection.connection_is_opened:
        self.is_running = True
        for i in range(len(self.axis)):
            self.connection.g.GMotionComplete(self.axis[i])
        self.motion_completed.emit()

    def check_for_motion(self, axis):
        # Result is 1 if axis is moving, zero if no movement
        result = int(float(self.connection.gcmd('MG _BG' + axis)))
        return result

    def stop(self):
        self.exit()
        self.is_running = False


class MyGamepadThread(qtc.QThread):
    # Signals
    jogged_forward = qtc.pyqtSignal()
    jogged_reverse = qtc.pyqtSignal()
    stopped_jog = qtc.pyqtSignal()
    scan_speed_updated = qtc.pyqtSignal(float)
    index_speed_updated = qtc.pyqtSignal(float)
    differential_updated = qtc.pyqtSignal(float)
    left_brake_applied = qtc.pyqtSignal()
    right_brake_applied = qtc.pyqtSignal()
    left_brake_released = qtc.pyqtSignal()
    right_brake_released = qtc.pyqtSignal()

    rotated_cw = qtc.pyqtSignal()
    rotated_ccw = qtc.pyqtSignal()
    stopped_rotation = qtc.pyqtSignal()

    jogged_left = qtc.pyqtSignal()
    jogged_right = qtc.pyqtSignal()
    stopped_scan = qtc.pyqtSignal()

    gamepad_disconnected = qtc.pyqtSignal()
    gamepad_connected = qtc.pyqtSignal()
    refresh_wait = 0.025

    def __init__(self, index_speed_signal, scan_speed_signal, enabled_index, enabled_scan):
        super(MyGamepadThread, self).__init__()
        self.index_restore_speed = 0
        self.scan_restore_speed = 0
        self.connected_last = tuple((False, False, False, False))
        self.index_speed_signal = index_speed_signal
        self.index_speed_signal.connect(self.update_index_restore_speed)
        self.scan_speed_signal = scan_speed_signal
        self.scan_speed_signal.connect(self.update_scan_restore_speed)
        self.enabled_index = enabled_index
        self.enabled_index.connect(self.update_enabled_status_for_index)
        self.is_index_enabled = False
        self.enabled_scan = enabled_scan
        self.enabled_scan.connect(self.update_enabled_status_for_scan)
        self.is_scan_enabled = False

        # State variables
        self.s_initial_move_forward = False
        self.s_initial_move_reverse = False
        self.s_final_forward_movement = False
        self.s_final_reverse_movement = False
        self.s_differential_changed = False
        self.s_index_stationary = True
        self.s_index_speed_changed = False  # Velocity change not resulting in state change

        self.s_initial_move_left = False
        self.s_initial_move_right = False
        self.s_final_left_movement = False
        self.s_final_right_movement = False
        self.s_scan_left_stationary = True
        self.s_scan_right_stationary = True
        self.s_left_scan_speed_changed = False
        self.s_right_scan_speed_changed = False

        self.s_in_rotation_mode = False
        self.s_initial_move_cw = False
        self.s_initial_move_ccw = False
        self.s_final_cw_movement = False
        self.s_final_ccw_movement = False
        self.s_rotation_stationary = True
        self.s_rotation_speed_changed = False  # Velocity change not resulting in state change

        self.s_left_brake = False
        self.s_left_brake_changed = False
        self.s_right_brake = False
        self.s_right_brake_changed = False

        self.scan_jog_speed_left = 0
        self.scan_jog_speed_right = 0
        self.index_jog_speed = 0
        self.differential = 0
        self.rotation_speed = 0

        self.btn_state_last = None
        self.thumb_state_last = None
        self.trigger_state_last = None

    def update_index_restore_speed(self, speed):
        if DEBUG:
            print("# INDEX restore speed received")
        self.index_restore_speed = speed

    def update_scan_restore_speed(self, speed):
        if DEBUG:
            print("# SCAN restore speed received")
        self.scan_restore_speed = speed

    def update_enabled_status_for_index(self, state):
        if DEBUG:
            print("# Setting Gamepad INDEX to be:", state)
        self.is_index_enabled = state

    def update_enabled_status_for_scan(self, state):
        if DEBUG:
            print("# Setting Gamepad SCAN to be:", state)
        self.is_scan_enabled = state

    def run(self):
        while True:
            time.sleep(self.refresh_wait)

            try:
                query_connections = get_connected()
                if query_connections.count(True) == 1:
                    index = query_connections.index(True)
                    state = get_state(index)

                    btn_state = get_button_values(state)
                    thumb_state = get_thumb_values(state)
                    trigger_state = get_trigger_values(state)

                    if self.btn_state_last is not None and self.thumb_state_last is not None and self.trigger_state_last is not None:
                        # Check if sticks are centered and the last movement was with the rotation thumb stick
                        if thumb_state[0][1] == 0 and thumb_state[1][0] == 0 and self.thumb_state_last[1][0]:
                            self.s_in_rotation_mode = True
                        # If both sticks are zero and there was no last movement, switch out of rotation mode
                        elif thumb_state[0][1] == 0 and thumb_state[1][0] == 0 and not self.thumb_state_last[1][0]:
                            self.s_in_rotation_mode = False
                        # Jog stick is stationary rotation stick is deflected, enter rotation mode
                        elif thumb_state[0][1] == 0 and thumb_state[1][0]:
                            self.s_in_rotation_mode = True

                        # Determine if tool is not moving for each axis
                        if thumb_state[0][1] == 0:
                            self.s_index_stationary = True
                        else:
                            self.s_index_stationary = False
                        if thumb_state[1][0] == 0:
                            self.s_rotation_stationary = True
                        else:
                            self.s_rotation_stationary = False
                        if trigger_state[0] == 0:
                            self.s_scan_left_stationary = True
                        else:
                            self.s_scan_left_stationary = False
                        if trigger_state[1] == 0:
                            self.s_scan_right_stationary = True
                        else:
                            self.s_scan_right_stationary = False

                        # Set the state of each brake
                        self.s_left_brake = btn_state['X']
                        self.s_right_brake = btn_state['B']

                        # Determine if the brake status changed
                        if btn_state['X'] != self.btn_state_last['X']:
                            self.s_left_brake_changed = True
                        else:
                            self.s_left_brake_changed = False

                        if btn_state['B'] != self.btn_state_last['B']:
                            self.s_right_brake_changed = True
                        else:
                            self.s_right_brake_changed = False

                        # Check if index movement from stationary
                        if self.thumb_state_last[0][1] == 0 and thumb_state[0][1] > 0:
                            self.s_initial_move_forward = True
                        else:
                            self.s_initial_move_forward = False

                        if self.thumb_state_last[0][1] == 0 and thumb_state[0][1] < 0:
                            self.s_initial_move_reverse = True
                        else:
                            self.s_initial_move_reverse = False

                        # Check if rotation movement from stationary
                        if self.thumb_state_last[1][0] == 0 and thumb_state[1][0] > 0:
                            self.s_initial_move_cw = True
                        else:
                            self.s_initial_move_cw = False

                        if self.thumb_state_last[1][0] == 0 and thumb_state[1][0] < 0:
                            self.s_initial_move_ccw = True
                        else:
                            self.s_initial_move_ccw = False

                        # Check if scan movement from stationary
                        if self.trigger_state_last[0] == 0 and trigger_state[0] > 0:
                            self.s_initial_move_left = True
                        else:
                            self.s_initial_move_left = False
                        if self.trigger_state_last[1] == 0 and trigger_state[1] > 0:
                            self.s_initial_move_right = True
                        else:
                            self.s_initial_move_right = False

                        # Check if final index movement
                        if self.thumb_state_last[0][1] > 0 and thumb_state[0][1] == 0:
                            self.s_final_forward_movement = True
                        else:
                            self.s_final_forward_movement = False

                        if self.thumb_state_last[0][1] < 0 and thumb_state[0][1] == 0:
                            self.s_final_reverse_movement = True
                        else:
                            self.s_final_reverse_movement = False

                        # Check if final rotation movement
                        if self.thumb_state_last[1][0] > 0 and thumb_state[1][0] == 0:
                            self.s_final_cw_movement = True
                        else:
                            self.s_final_cw_movement = False

                        if self.thumb_state_last[1][0] < 0 and thumb_state[1][0] == 0:
                            self.s_final_ccw_movement = True
                        else:
                            self.s_final_ccw_movement = False

                        # Check if final scan movement
                        if self.trigger_state_last[0] > 0 and trigger_state[0] == 0:
                            self.s_final_left_movement = True
                        else:
                            self.s_final_left_movement = False
                        if self.trigger_state_last[1] > 0 and trigger_state[1] == 0:
                            self.s_final_right_movement = True
                        else:
                            self.s_final_right_movement = False

                        # Check for index speed change
                        if self.thumb_state_last[0][1] >= 0 and thumb_state[0][1] >= 0:
                            if self.thumb_state_last[0][1] != thumb_state[0][1]:
                                self.s_index_speed_changed = True
                            else:
                                self.s_index_speed_changed = False
                        if self.thumb_state_last[0][1] < 0 and thumb_state[0][1] < 0:
                            if self.thumb_state_last[0][1] != thumb_state[0][1]:
                                self.s_index_speed_changed = True
                            else:
                                self.s_index_speed_changed = False

                        # Check for rotation speed change
                        if self.thumb_state_last[1][0] >= 0 and thumb_state[1][0] >= 0:
                            if self.thumb_state_last[1][0] != thumb_state[1][0]:
                                self.s_rotation_speed_changed = True
                            else:
                                self.s_rotation_speed_changed = False
                        if self.thumb_state_last[1][0] <= 0 and thumb_state[1][0] <= 0:
                            if self.thumb_state_last[1][0] != thumb_state[1][0]:
                                self.s_rotation_speed_changed = True
                            else:
                                self.s_rotation_speed_changed = False

                        # Check for scan speed change
                        if self.trigger_state_last[0] >= 0 and trigger_state[0] >= 0:
                            if self.trigger_state_last[0] != trigger_state[0]:
                                self.s_left_scan_speed_changed = True
                            else:
                                self.s_left_scan_speed_changed = False

                        if self.trigger_state_last[1] >= 0 and trigger_state[1] >= 0:
                            if self.trigger_state_last[1] != trigger_state[1]:
                                self.s_right_scan_speed_changed = True
                            else:
                                self.s_right_scan_speed_changed = False

                        # Check for differential change
                        if self.thumb_state_last[0][0] > 0 and thumb_state[0][0] > 0:
                            if self.thumb_state_last[0][0] != thumb_state[0][0]:
                                self.s_differential_changed = True
                            else:
                                self.s_differential_changed = False
                        if self.thumb_state_last[0][0] < 0 and thumb_state[0][0] < 0:
                            if self.thumb_state_last[0][0] != thumb_state[0][0]:
                                self.s_differential_changed = True
                            else:
                                self.s_differential_changed = False
                        if thumb_state[0][0] == 0 and self.thumb_state_last[0][0] != 0:
                            self.s_differential_changed = True

                        # Set the speeds
                        self.scan_jog_speed_left = trigger_state[0]
                        self.scan_jog_speed_right = trigger_state[1]
                        self.index_jog_speed = thumb_state[0][1]
                        self.rotation_speed = thumb_state[1][0]
                        self.differential = thumb_state[0][0]

                        # Apply Signals based on change of state variables
                        if self.is_index_enabled:
                            self.calculate_state_change_for_index()
                        if self.is_scan_enabled:
                            self.calculate_state_change_for_scan()

                    self.thumb_state_last = thumb_state
                    self.btn_state_last = btn_state
                    self.trigger_state_last = trigger_state

                # Check if gamepad was disconnected and stop movement. Also don't allow for multiple gamepads
                if query_connections != self.connected_last:
                    new_count = query_connections.count(True)
                    old_count = self.connected_last.count(True)
                    if new_count < old_count:
                        self.gamepad_disconnected.emit()
                        self.index_speed_updated.emit(self.index_restore_speed)
                        self.scan_speed_updated.emit(self.scan_restore_speed)
                    elif new_count > 1:
                        self.gamepad_disconnected.emit()
                        self.index_speed_updated.emit(self.index_restore_speed)
                        self.scan_speed_updated.emit(self.scan_restore_speed)
                    elif new_count == 1:
                        self.gamepad_connected.emit()
                    self.connected_last = query_connections

            except:
                print("# Problem with Gamepad")

    def calculate_state_change_for_scan(self):
        # Check to make sure user is only pressing one trigger for scan axis
        if not self.s_scan_left_stationary and not self.s_scan_right_stationary:
            self.stopped_scan.emit()
            self.scan_speed_updated.emit(self.scan_restore_speed)
        # Only one trigger is pressed, proceed with checks
        else:
            if self.s_initial_move_left or self.s_initial_move_right:
                if self.s_initial_move_left:
                    self.jogged_left.emit()
                    self.scan_speed_updated.emit(self.scan_jog_speed_left)
                elif self.s_initial_move_right:
                    self.jogged_right.emit()
                    self.scan_speed_updated.emit(self.scan_jog_speed_right)

            if self.s_left_scan_speed_changed:
                self.scan_speed_updated.emit(self.scan_jog_speed_left)
            if self.s_right_scan_speed_changed:
                self.scan_speed_updated.emit(self.scan_jog_speed_right)
            if self.s_final_left_movement or self.s_final_right_movement:
                self.stopped_scan.emit()
                self.scan_speed_updated.emit(self.scan_restore_speed)

    def calculate_state_change_for_index(self):
        # Check for movement started from stopped position
        if not self.s_in_rotation_mode:
            if self.s_initial_move_forward or self.s_initial_move_reverse:
                self.index_speed_updated.emit(self.index_jog_speed)
                if self.s_initial_move_forward:
                    self.jogged_forward.emit()
                    if DEBUG:
                        print("# Jogging Forward")

                    # Allow for single or double braking at start of movement
                    if self.s_left_brake:
                        self.left_brake_applied.emit()
                        if DEBUG:
                            print("# Applied Left Brake")
                    if self.s_right_brake:
                        self.right_brake_applied.emit()
                        if DEBUG:
                            print("# Applied Right Brake")
                else:
                    self.jogged_reverse.emit()
                    if DEBUG:
                        print("# Jogging Reverse")

                    # Allow for single or double braking at start of movement
                    if self.s_left_brake:
                        self.left_brake_applied.emit()
                        if DEBUG:
                            print("# Applied Left Brake")
                    if self.s_right_brake:
                        self.right_brake_applied.emit()
                        if DEBUG:
                            print("# Applied Right Brake")

            # Velocity change with no state change, i.e. going forward and want to go forward faster
            if self.s_index_speed_changed:
                self.index_speed_updated.emit(self.index_jog_speed)

            # Update the differential horizontal slider bar
            if self.s_differential_changed:
                self.differential_updated.emit(self.differential)

            # Check for movement to stop
            if self.s_final_forward_movement or self.s_final_reverse_movement:
                if self.s_final_forward_movement:
                    if DEBUG:
                        print("# Stopped Jog from Forward")
                else:
                    if DEBUG:
                        print("# Stopped Jog from Reverse")
                self.stopped_jog.emit()
                # Restore GUI velocity to value before activating gamepad
                self.index_speed_updated.emit(self.index_restore_speed)

            # Check for change in braking but do nothing if stationary
            if (self.s_left_brake_changed or self.s_right_brake_changed) and not self.s_index_stationary:
                # Check if the left brake had the state change
                if self.s_left_brake_changed:
                    if self.s_left_brake:
                        self.left_brake_applied.emit()
                        if DEBUG:
                            print("# Left Brake Applied")
                    else:
                        self.left_brake_released.emit()
                        if DEBUG:
                            print("# Left Brake Released")

                if self.s_right_brake_changed:
                    if self.s_right_brake:
                        self.right_brake_applied.emit()
                        if DEBUG:
                            print("# Right Brake Applied")
                    else:
                        self.right_brake_released.emit()
                        if DEBUG:
                            print("# Right Brake Released")
        else:
            if self.s_initial_move_cw or self.s_initial_move_ccw:
                self.index_speed_updated.emit(self.rotation_speed)
                if self.s_initial_move_cw:
                    self.rotated_cw.emit()
                    if DEBUG:
                        print("# CW Motion")
                else:
                    self.rotated_ccw.emit()
                    if DEBUG:
                        print("# CCW Motion")

            if self.s_rotation_speed_changed:
                self.index_speed_updated.emit(self.rotation_speed)

            if self.s_final_cw_movement or self.s_final_ccw_movement:
                if self.s_final_cw_movement:
                    if DEBUG:
                        print("# Stopped CW Rotation")
                else:
                    if DEBUG:
                        print("# Stopped CCW Rotation")
                self.stopped_rotation.emit()
                # Restore GUI velocity to value before activating gamepad
                self.index_speed_updated.emit(self.index_restore_speed)

    def stop(self):
        if DEBUG:
            print("# Gamepad thread terminated")
        self.exit()
        self.gamepad_disconnected.emit()
        # Restore GUI velocity to value before activating gamepad
        self.index_speed_updated.emit(self.index_restore_speed)
        self.scan_speed_updated.emit(self.scan_restore_speed)
        self.connected_last = tuple((False, False, False, False))
        self.btn_state_last = None
        self.thumb_state_last = None
        self.trigger_state_last = None


if __name__ == '__main__':
    app = qtw.QApplication([])
    mw = UserWindow()
    mw.show()
    app.exec_()
