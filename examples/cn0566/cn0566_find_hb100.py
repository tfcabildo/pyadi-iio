#!/usr/bin/env python3
#  Must use Python 3
# Copyright (C) 2022 Analog Devices, Inc.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#     - Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     - Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in
#       the documentation and/or other materials provided with the
#       distribution.
#     - Neither the name of Analog Devices, Inc. nor the names of its
#       contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#     - The use of this software may or may not infringe the patent rights
#       of one or more patent holders.  This license does not release you
#       from the requirement that you obtain separate licenses from these
#       patent holders to use this software.
#     - Use of the software either in source or binary form, must be run
#       on or directly connected to an Analog Devices Inc. component.
#
# THIS SOFTWARE IS PROVIDED BY ANALOG DEVICES "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, NON-INFRINGEMENT, MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED.
#
# IN NO EVENT SHALL ANALOG DEVICES BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, INTELLECTUAL PROPERTY
# RIGHTS, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
# THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


# Utility script to find the frequency of an HB100 microwave source.
# Also serves as basic example for setting / stepping the frequency of
# the phaser's PLL, capturing data, calculating FFTs, and stitching together
# FFTs that span several bands.


import os
import pickle
import sys
import time
from time import sleep

import matplotlib.pyplot as plt
import numpy as np
from cn0566_functions import save_hb100_cal, spec_est
from scipy import signal

if os.name == "nt":  # Assume running on Windows
    rpi_ip = "ip:phaser.local"  # IP address of the remote Raspberry Pi
    #     rpi_ip = "ip:169.254.225.48" # Hard code an IP here for debug
    sdr_ip = "ip:pluto.local"  # Pluto IP, with modified IP address or not
    print("Running on Windows, connecting to ", rpi_ip, " and ", sdr_ip)
elif os.name == "posix":
    rpi_ip = "ip:localhost"  # Assume running locally on Raspberry Pi
    sdr_ip = "ip:192.168.2.1"  # Historical - assume default Pluto IP
    print("Running on Linux, connecting to ", rpi_ip, " and ", sdr_ip)
else:
    print("Can't detect OS")

try:
    x = my_sdr.uri
    print("Pluto already connected")
except NameError:
    print("Pluto not connected, connecting...")
    from adi import ad9361

    my_sdr = ad9361(uri=sdr_ip)

time.sleep(0.5)

try:
    x = my_phaser.uri
    print("cn0566 already connected")
except NameError:
    print("cn0566 not connected, connecting...")
    from adi.cn0566 import CN0566

    my_phaser = CN0566(uri=rpi_ip, rx_dev=my_sdr)


#  Configure SDR parameters.

my_sdr._ctrl.debug_attrs["adi,frequency-division-duplex-mode-enable"].value = "1"
my_sdr._ctrl.debug_attrs[
    "adi,ensm-enable-txnrx-control-enable"
].value = "0"  # Disable pin control so spi can move the states
my_sdr._ctrl.debug_attrs["initialize"].value = "1"

my_sdr.rx_enabled_channels = [0, 1]  # enable Rx1 (voltage0) and Rx2 (voltage1)
my_sdr._rxadc.set_kernel_buffers_count(1)  # No stale buffers to flush
rx = my_sdr._ctrl.find_channel("voltage0")
rx.attrs["quadrature_tracking_en"].value = "1"  # enable quadrature tracking
my_sdr.sample_rate = int(30000000)  # Sampling rate
my_sdr.rx_buffer_size = int(4 * 256)
my_sdr.rx_rf_bandwidth = int(10e6)
# We must be in manual gain control mode (otherwise we won't see the peaks and nulls!)
my_sdr.gain_control_mode_chan0 = "manual"  # DISable AGC
my_sdr.gain_control_mode_chan1 = "manual"
my_sdr.rx_hardwaregain_chan0 = 0  # dB
my_sdr.rx_hardwaregain_chan1 = 0  # dB

my_sdr.rx_lo = int(2.0e9)  # Downconvert by 2GHz  # Recieve Freq

my_sdr.filter = "LTE20_MHz.ftr"  # Handy filter for fairly widdeband measurements

# Make sure the Tx channels are attenuated (or off) and their freq is far away from Rx
# this is a negative number between 0 and -88
my_sdr.tx_hardwaregain_chan0 = int(-80)
my_sdr.tx_hardwaregain_chan1 = int(-80)


# Configure CN0566 parameters.
#     ADF4159 and ADAR1000 array attributes are exposed directly, although normally
#     accessed through other methods.

# By default device_mode is "rx"
my_phaser.configure(device_mode="rx")

# Set initial PLL frequency to HB100 nominal

my_phaser.SignalFreq = 10.525e9

# Onboard source w/ external Vivaldi
my_phaser.frequency = (
    int(my_phaser.SignalFreq) + my_sdr.rx_lo
) // 4  # PLL feedback via /4 VCO output
my_phaser.freq_dev_step = 5690
my_phaser.freq_dev_range = 0
my_phaser.freq_dev_time = 0
my_phaser.powerdown = 0
my_phaser.ramp_mode = "disabled"

# Set all elements to half scale - a typical HB100 will have plenty
# of signal power.

gain_list = [64] * 8
for i in range(0, len(gain_list)):
    my_phaser.set_chan_gain(i, gain_list[i], apply_cal=False)

# Aim the beam at boresight (zero degrees). Place HB100 right in front of array.
my_phaser.set_beam_phase_diff(0.0)

# Averages decide number of time samples are taken to plot and/or calibrate system. By default it is 1.
my_phaser.Averages = 8

# Initialize arrays for amplitudes, frequencies
full_ampl = np.empty(0)
full_freqs = np.empty(0)

# Set up range of frequencies to sweep. Sample rate is set to 30Msps,
# for a total of 30MHz of bandwidth (quadrature sampling)
# Filter is 20MHz LTE, so you get a bit less than 20MHz of usable
# bandwidth. Set step size to something less than 20MHz to ensure
# complete coverage.
f_start = 10.0e9
f_stop = 10.7e9
f_step = 10e6

for freq in range(int(f_start), int(f_stop), int(f_step)):
    #    print("frequency: ", freq)
    my_phaser.SignalFreq = freq
    my_phaser.frequency = (
        int(my_phaser.SignalFreq) + my_sdr.rx_lo
    ) // 4  # PLL feedback via /4 VCO output

    data = my_sdr.rx()
    data_sum = data[0] + data[1]
    #    max0 = np.max(abs(data[0]))
    #    max1 = np.max(abs(data[1]))
    #    print("max signals: ", max0, max1)
    ampl, freqs = spec_est(data_sum, 30000000, ref=2 ^ 12, plot=False)
    ampl = np.fft.fftshift(ampl)
    ampl = np.flip(ampl)  # Just an experiment...
    freqs = np.fft.fftshift(freqs)
    freqs += freq
    full_freqs = np.concatenate((full_freqs, freqs))
    full_ampl = np.concatenate((full_ampl, ampl))
    sleep(0.1)
full_freqs /= 1e9  # Hz -> GHz

peak_index = np.argmax(full_ampl)
peak_freq = full_freqs[peak_index]
print("Peak frequency found at ", full_freqs[peak_index], " GHz.")

plt.figure(2)
plt.title("Full Spectrum, peak at " + str(full_freqs[peak_index]) + " GHz.")
plt.plot(full_freqs, full_ampl, linestyle="", marker="o", ms=2)
plt.xlabel("Frequency [GHz]")
plt.ylabel("Signal Strength")
plt.show()
print("You may need to close plot to continue...")

prompt = input("Save cal file? (y or n)")
if prompt.upper() == "Y":
    save_hb100_cal(peak_freq * 1e9)

del my_sdr
del my_phaser