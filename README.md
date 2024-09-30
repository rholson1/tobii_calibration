# tobii_calibration
Tobii eye tracker calibration script for use with infants.

Running the script will open a window with widgets to select the eye tracker, choose which monitor should be used
for the calibration display, and start the calibration.  Additionally, once the eye tracker has been selected, the
current gaze position and eye position can be displayed.

The following dependencies can be installed using pip:
* tobii-research==1.11.0
* screeninfo
* pyaudio

During calibration, a dot moves across the screen to several calibration points, where it then shrinks and swells.  An
audio file is played when the dot reaches each calibration point.


