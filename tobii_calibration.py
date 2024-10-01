import tkinter as tk
from tkinter import ttk, messagebox

import tobii_research as tr
import time
import math
from math import isnan, copysign, isclose
import random
from enum import Enum
from functools import partial

from screeninfo import get_monitors
import pyaudio
import wave

VERSION_MAJOR = 1
VERSION_MINOR = 0

FAKE_CALIBRATION = False  # allows calibration to run without eyetracker connection for testing
CALIBRATION_SOUND = 'calib_sound.wav'

class CalibrationState(Enum):
    MOVING = 1
    SHRINKING = 2
    GROWING = 3


CALIBRATION_AUDIO_DEVICE = 1  # Index of the audio device to use for calibration sounds (in range(PyAudio().get_device_count())

is_close = partial(isclose, abs_tol=0.001)

class MainApp:
    def __init__(self, parent):
        self.title = 'Tobii Calibration'

        self.window_title = f'{self.title} {VERSION_MAJOR}.{VERSION_MINOR}'

        self.parent = parent
        self.root = tk.Toplevel(parent)
        self.root.protocol('WM_DELETE_WINDOW', self.close_app)
        self.root.minsize(500, 500)

        self.et = None  # eyetracker object
        self.calibration = None  # calibration object
        self.wavdata = b''
        self.sound_cursor = 0
        self.pyaudio = None



        # variables for widgets
        self.et_var = tk.StringVar()
        self.eye_var = tk.IntVar()
        self.gaze_var = tk.IntVar()
        self.dist_var = tk.IntVar()
        self.screen_var = tk.StringVar()

        self.build_layout()
        self.load_sound()  # load sound to be used during calibration

        self.find_eyetrackers()
        self.find_screens()


    def close_app(self):
        self.parent.destroy()

    def build_layout(self):
        self.root.title(self.window_title)

        self.root.columnconfigure(1, weight=1)

        self.root.rowconfigure(1, weight=0)
        self.root.rowconfigure(2, weight=1)
        self.root.rowconfigure(3, weight=0)

        self.top_frame = tk.Frame(self.root)
        self.top_frame.grid(row=1, column=1, sticky='nsew')
        self.top_frame.rowconfigure(0, weight=1)
        self.top_frame.columnconfigure(0, weight=1)
        self.top_frame.columnconfigure(1, weight=1)
        self.top_frame.columnconfigure(2, weight=1)
        self.top_frame.columnconfigure(3, weight=1)

        self.canvas = tk.Canvas(self.root)
        self.canvas.grid(row=2, column=1, sticky='nsew')

        self.bottom_frame = tk.Frame(self.root)
        self.bottom_frame.grid(row=3, column=1, sticky='nsew')
        self.bottom_frame.rowconfigure(0, weight=1)
        self.bottom_frame.rowconfigure(1, weight=1)
        self.bottom_frame.columnconfigure(0, weight=0)
        self.bottom_frame.columnconfigure(1, weight=0)
        self.bottom_frame.columnconfigure(2, weight=1)




        self.canvas.configure(bg='white')


        # top controls

        ttk.Label(self.top_frame, text='ET').grid(row=0, column=0, sticky='nsew')
        self.et_combo = ttk.Combobox(self.top_frame, textvariable=self.et_var, state='readonly')
        self.et_combo.grid(row=0, column=1, sticky='nsew')
        self.et_combo.bind('<<ComboboxSelected>>', self.select_eyetracker)

        self.refresh_btn = ttk.Button(self.top_frame, text='Refresh', command=self.find_eyetrackers)
        self.refresh_btn.grid(row=0, column=2, sticky='nsew')
        # self.connect_btn = ttk.Button(self.top_frame, text='Connect')
        # self.connect_btn.grid(row=0, column=3, sticky='nsew')

        # bottom controls

        self.eyes_chk = tk.Checkbutton(self.bottom_frame, text='Eyes')
        self.eyes_chk.grid(row=0, column=0, sticky='nsew')

        self.gaze_chk = tk.Checkbutton(self.bottom_frame, text='Gaze')
        self.gaze_chk.grid(row=0, column=1, sticky='nsew')
        self.dist_bar = ttk.Progressbar(self.bottom_frame, mode='determinate', value=0)
        self.dist_bar.grid(row=0, column=2, sticky='nsew')
        self.dist_bar['value'] = 50

        ttk.Label(self.bottom_frame, text='Screen').grid(row=1, column=0, sticky='nsew')
        self.screen_cbo = ttk.Combobox(self.bottom_frame, textvariable=self.screen_var)
        self.screen_cbo.grid(row=1, column=1, sticky='nsew')

        self.calibrate_btn = ttk.Button(self.bottom_frame, text='Calibrate', command=self.calibrate)
        self.calibrate_btn.grid(row=1, column=2, sticky='nsew')

    def find_eyetrackers(self, e=None):
        # find the list of available eyetrackers
        eyetrackers = tr.find_all_eyetrackers()

        et_labels = ['_'.join([et.model, et.serial_number]) for et in eyetrackers]

        # for testing without an attached ET
        if FAKE_CALIBRATION:
            et_labels = ['Eyetracker_1', 'Eyetracker_2', 'Eyetracker_3', 'Eyetracker_4']
            random.shuffle(et_labels)

        # populate combobox
        self.et_combo['values'] = et_labels

        # if there is only one eyetracker, select it
        if len(et_labels) == 1:
            self.et_var.set(et_labels[0])
            self.select_eyetracker()

    def find_screens(self):
        screens = get_monitors()
        screen_labels = [s.name for s in screens]
        self.screen_cbo['values'] = screen_labels

        # if there is only one screen, select it
        if len(screens) == 1:
            self.screen_cbo.set(screen_labels[0])


    def select_eyetracker(self, e=None):
        selected_idx = self.et_combo.current()

        serial_number = self.et_var.get().split('_', 1)[1]

        # search by serial number
        eyetrackers = tr.find_all_eyetrackers()
        selected_et = [et for et in eyetrackers if et.serial_number == serial_number]
        if selected_et:
            self.et = selected_et[0]
            # subscribe to ET events
            self.et.subscribe_to(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback, as_dictionary=True)

        else:
            raise Exception('The selected eye tracker does not exist')


    def gaze_data_callback(self, data):

        if self.gaze_var.get() == 1:
            gaze_left = data['left_gaze_point_on_display_area']
            gaze_right = data['right_gaze_point_on_display_area']
            if isnan(gaze_left) and isnan(gaze_right):
                pass  # no data to plot
            elif isnan(gaze_left):
                self.plot_gaze(*gaze_right)
            elif isnan(gaze_right):
                self.plot_gaze(*gaze_left)
            else:
                # compute average of left and right eye gaze positions
                self.plot_gaze((gaze_left[0] + gaze_right[0])/2,
                               (gaze_left[1] + gaze_right[1])/2)


        if self.eye_var.get() == 1:
            # plot eye position TBD
            pass

        # Update dist_bar to show position in z-coordinates track box coordinate system
        # (normalized with 0 closest to ET and 1 farthest)

        # position in track box
        left_eye_z = data['left_gaze_origin_in_trackbox_coordinate_system'][2]
        right_eye_z = data['right_gaze_origin_in_trackbox_coordinate_system'][2]

        if isnan(left_eye_z) and isnan(right_eye_z):
            self.dist_bar['value'] = 0  # maybe should signify no track somehow (color?)
        elif isnan(left_eye_z):
            self.dist_bar['value'] = 100 * right_eye_z
        elif isnan(right_eye_z):
            self.dist_bar['value'] = 100 * left_eye_z
        else:
            # neither left nor right are nan, so use average
            self.dist_bar['value'] = 50 * (left_eye_z + right_eye_z)



    #
    # sample_gaze_data = {
    #     'device_time_stamp': 5456302102725,
    #     'system_time_stamp': 986645801748,
    #     'left_gaze_point_on_display_area': (nan, nan),
    #     'left_gaze_point_in_user_coordinate_system': (nan, nan, nan),
    #     'left_gaze_point_validity': 0,
    #     'left_pupil_diameter': nan,
    #     'left_pupil_validity': 0,
    #     'left_gaze_origin_in_user_coordinate_system': (nan, nan, nan),
    #     'left_gaze_origin_in_trackbox_coordinate_system': (nan, nan, nan),
    #     'left_gaze_origin_validity': 0,
    #     'right_gaze_point_on_display_area': (nan, nan),
    #     'right_gaze_point_in_user_coordinate_system': (nan, nan, nan),
    #     'right_gaze_point_validity': 0,
    #     'right_pupil_diameter': nan,
    #     'right_pupil_validity': 0,
    #     'right_gaze_origin_in_user_coordinate_system': (nan, nan, nan),
    #     'right_gaze_origin_in_trackbox_coordinate_system': (nan, nan, nan),
    #     'right_gaze_origin_validity': 0}


    def plot_gaze(self, x, y):
        """Draw the gaze position in the main window canvas"""
        RADIUS = 10  # px?
        self.canvas.create_oval(x-RADIUS, y-RADIUS, x+RADIUS, y+RADIUS)


    def calibrate(self, e=None):

        # example of getting the size of a canvas widget.  In our case, since fullscreen, should be able to use
        # the screen height and width.
        # self.parent.update()
        # print(self.canvas.winfo_width(), self.canvas.winfo_height())
        # print(self.canvas.winfo_geometry())
        #
        # return

        self.pyaudio = pyaudio.PyAudio()

        # Create a calibration window fullscreen on the selected monitor.
        screens = get_monitors()
        screen = [s for s in screens if s.name == self.screen_cbo.get()][0]
        # notable properties of screen include x, y, width, height

        self.calib_window = tk.Toplevel(self.parent)  # create new toplevel window
        self.calib_window.geometry(f'+{screen.x}+{screen.y}')  # position window on the selected screen
        self.calib_window.attributes('-fullscreen', True)  # make window fullscreen
        self.calib_window.grid_columnconfigure(0, weight=1)
        self.calib_window.grid_rowconfigure(0, weight=1)

        self.calibcanvas = tk.Canvas(self.calib_window)
        self.calibcanvas.grid(row=0, column=0, sticky='nsew')

        self.parent.update()
        self.calib_width = self.calibcanvas.winfo_width()
        self.calib_height = self.calibcanvas.winfo_height()

        # 5-point calibration
        self.calib_targets = [[0.1, 0.2], [0.9, 0.2], [0.1, 0.9], [0.9, 0.9], [0.5, 0.5]]
        self.calib_r_max = 30
        self.calib_r_min = 2
        self.calib_pos = [0.2, 0.6]  # initial position
        self.calib_r = 30  # initial point radius
        self.calib_index = 0  # index of next calibration point
        self.calib_state = CalibrationState.MOVING


        self.draw_calib_dot(*self.calib_pos, self.calib_r, create=True)

        if not FAKE_CALIBRATION:
            self.calibration = tr.ScreenBasedCalibration(self.et)
            self.calibration.enter_calibration_mode()

        self.run_calibration()



        # canvas.create_rectangle(0, 0, screen.width/2, screen.height/2, fill='red')
        # self.calib_window.after(4000, self.close_calibration)

    def draw_calib_dot(self, x, y, r, create=False):
        """Draw the calib guide dot in the calibration canvas.

        x, y supplied in normalized coordinates (0-1), and r is in pixels.
        :param x: x-coordinate of guide dot in normalized coordinates (0-1)
        :param y: y-coordinate of guide dot in normalized coordinates (0-1)
        :param r: radius of guide dot in pixels
        :param create: If True, create new dot.  If False, reposition existing dot.
        """
        xx = x * self.calib_width
        yy = y * self.calib_height
        if create:
            self.calib_dot = self.calibcanvas.create_oval(xx - r, yy - r, xx + r, yy + r, fill='red')
        else:
            self.calibcanvas.coords(self.calib_dot, xx - r, yy - r, xx + r, yy + r)


    def run_calibration(self):
        """
        Calibration trajectory:
        move to target.
        shrink
        collect calibration data
        grow
        move to next target


        :return:
        """
        DELAY = 50  # ms
        STEP = 0.02
        STEP_R = 2  # px


        if self.calib_state == CalibrationState.MOVING:
            if (is_close(self.calib_pos[0], self.calib_targets[self.calib_index][0])
                    and is_close(self.calib_pos[1], self.calib_targets[self.calib_index][1])):
                self.calib_state = CalibrationState.SHRINKING
                self.play_sound()
            else:
                # move
                diff_x = self.calib_targets[self.calib_index][0] - self.calib_pos[0]
                diff_y = self.calib_targets[self.calib_index][1] - self.calib_pos[1]
                if not is_close(diff_x, 0) :
                    self.calib_pos[0] += copysign(STEP, diff_x)
                if not is_close(diff_y, 0):
                    self.calib_pos[1] += copysign(STEP, diff_y)

                self.draw_calib_dot(*self.calib_pos, self.calib_r)

        elif self.calib_state == CalibrationState.SHRINKING:
            if is_close(self.calib_r, self.calib_r_min):

                # collect calibration data (try a second time if the first time fails)
                if not FAKE_CALIBRATION:
                    if self.calibration.collect_data(*self.calib_pos) != tr.CALIBRATION_STATUS_SUCCESS:
                        self.calibration.collect_data(*self.calib_pos)

                self.calib_state = CalibrationState.GROWING
            else:
                self.calib_r -= STEP_R
                self.draw_calib_dot(*self.calib_pos, self.calib_r)

        elif self.calib_state == CalibrationState.GROWING:
            if is_close(self.calib_r, self.calib_r_max):
                if self.calib_index == len(self.calib_targets) - 1:
                    # Done with calibration!
                    self.close_calibration()
                else:
                    self.calib_index += 1
                    self.calib_state = CalibrationState.MOVING
            else:
                self.calib_r += STEP_R
                self.draw_calib_dot(*self.calib_pos, self.calib_r)
        else:
            raise Exception(f'Invalid calibration state: {self.calib_state}')

        self.calib_window.after(DELAY, self.run_calibration)

    def close_calibration(self):

        # complete calibration
        if not FAKE_CALIBRATION:
            try:
                self.calibration.compute_and_apply()
                self.calibration.leave_calibration_mode()
            except Exception as e:
                messagebox.showerror(message=str(e), title='Calibration error')


        self.calib_window.destroy()


    def load_sound(self):
        # load a wav file (calibsound.wav) to play during calibration
        wf = wave.open(CALIBRATION_SOUND, 'rb')
        self.wave_samplewidth = wf.getsampwidth()
        self.wave_channels = wf.getnchannels()
        self.wave_framerate = wf.getframerate()
        data = wf.readframes(1024)
        while len(data) > 0:
            self.wavdata += data
            data = wf.readframes(1024)
        wf.close()


    def gen_sound(self):
        # Generate a sound to be played during calibration
        BITRATE = 16000.
        FREQ = 600. # Hz
        LENGTH = 1.0 # s

        frames = int(BITRATE * LENGTH)
        padding = frames % int(BITRATE)
        #wavdata = ''

        for x in range(frames):
            self.wavdata += chr(int(
                (
                    math.sin(x * (FREQ * x/frames) / BITRATE * math.pi) *
                    math.sin(x * (FREQ * math.cos(x / frames * math.pi)) / BITRATE * math.pi)
                 ) * 50 + 128  # * 127 + 128 tweak these numbers to increase or decrease the volume
            ))
        last = self.wavdata[-1]
        for x in range(padding):
            self.wavdata += last  # chr(128)

        self.wave_samplewidth = 1
        self.wave_channels = 1
        self.wave_framerate = BITRATE

    def sound_callback(self, in_data, frame_count, time_info, status):
        seg_len = frame_count * self.wave_samplewidth * self.wave_channels
        if seg_len + self.sound_cursor >= len(self.wavdata):
            response = pyaudio.paComplete
        else:
            response = pyaudio.paContinue
        out_data = self.wavdata[self.sound_cursor:self.sound_cursor + seg_len]
        self.sound_cursor += seg_len
        return out_data, response

    def play_sound(self):
        self.sound_cursor = 0
        stream = self.pyaudio.open(format=self.pyaudio.get_format_from_width(self.wave_samplewidth),
                                   channels=self.wave_channels,
                                   rate=int(self.wave_framerate),
                                   output=True,
                                   output_device_index=CALIBRATION_AUDIO_DEVICE,
                                   stream_callback=self.sound_callback)
        stream.start_stream()
        return False

if __name__ == '__main__':


    root = tk.Tk()
    root.withdraw()

    app = MainApp(root)
    root.mainloop()
