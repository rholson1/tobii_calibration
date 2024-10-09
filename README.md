# tobii_calibration
Tobii eye tracker calibration script for use with infants.

Running the script will open a window with widgets to select the eye tracker, choose which monitor should be used
for the calibration display, and start the calibration.  Additionally, once the eye tracker has been selected, the
current gaze position and eye position can be displayed.

The Tobii Pro SDK currently (9/2024) only supports **Python 3.10**.  

The following dependencies can be installed using pip:
* tobii-research
* screeninfo
* pyaudio

During calibration, a dot moves across the screen to several calibration points, where it then shrinks and swells.  An
audio file is played when the dot reaches each calibration point.

The audio device is selected by setting the value of CALIBRATION_AUDIO_DEVICE near the top of tobii_calibration.py.


