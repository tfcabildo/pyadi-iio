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

import numpy as np
from adi.ad9083 import ad9083
from adi.adf4371 import adf4371
from adi.adl5960 import adl5960
from adi.admv8818 import admv8818
from adi.adrf5720 import adrf5720
from adi.gen_mux import genmux
from adi.one_bit_adc_dac import one_bit_adc_dac
from adi.ad9173 import ad9173
from adi.ad5686 import ad5686
from adi.ad4858 import ad4858

class fmc_4p_vna(adrf5720, ad9083, admv8818, genmux, adf4371, adl5960, one_bit_adc_dac):
    """ FMCVNA Scalable 4-port Vector Network Analyzer Board """

    frontend = [0] * 8

    def __init__(self, uri):
        self.lo = adf4371(uri)
        self.rfin_attenuator = adrf5720(uri, device_name="adrf5720-rfin")
        self.lo_attenuator = adrf5720(uri, device_name="adrf5720-lo")
        self.bpf = admv8818(uri, device_name="admv8818")
        self.rfin_mux = genmux(uri, device_name="mux-rfin")
        self.lo_mux = genmux(uri, device_name="mux-adf4371")
        self.freq_src_sel_mux = genmux(uri, device_name="mux-freq-src-sel")
        self.rfin_freq_src_sel_mux = genmux(uri, device_name="mux-rfin-freq-src-sel")
        self.hsdac = ad9173(uri)
        self.ad4858 = ad4858(uri)
        self.ad5732 = ad5686(uri)

        for i in range(1, 5):
            self.frontend[i - 1] = adl5960(uri, device_name=f"adl5960-{i}")

        ad9083.__init__(self, uri)
        one_bit_adc_dac.__init__(self, uri)

        self._rxadc.set_kernel_buffers_count(1)
        self.ad4858._rxadc.set_kernel_buffers_count(1)