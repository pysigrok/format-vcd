"""PySigrok driver for value change dump (VCD)"""

__version__ = "0.1.1"

import io
from operator import itemgetter
import vcd

from sigrokdecode.output import Output

class VCDOutput(Output):
    name = "vcd"
    desc = "Value change dump"

    def __init__(self, openfile, driver, logic_channels=[], analog_channels=[], decoders=[]):
        self.logic_channels = logic_channels
        self.samplenum = 0
        timescale = "1 fs"
        if driver.samplerate == 10000000:
            timescale = "100 ns"
        self.writer = vcd.VCDWriter(io.TextIOWrapper(openfile), timescale=timescale, date="today", comment="pysigrok output")
        self.vars = []
        self.buffered_changes = []
        for chan in logic_channels:
            self.vars.append(self.writer.register_var(driver.name, chan, "wire", size=1))
        self.analog_vars = []
        for chan in analog_channels:
            self.analog_vars.append(self.writer.register_var(driver.name, chan, "real", size=4))

        self.annotation_row_vars = {}

    def output(self, source, startsample, endsample, data):
        ptype = data[0]
        if ptype == "logic":
            for bit, var in enumerate(self.vars):
                val = (data[1] & (1 << bit)) != 0
                self.buffered_changes.append((var, startsample, True, val))

        elif ptype == "analog":
            for i, v in enumerate(data[1:]):
                self.buffered_changes.append((self.analog_vars[i], startsample, True, v))
        else:
            # annotation
            if source not in self.annotation_row_vars:
                decoder_rows = [None] * len(source.annotations)
                for row_id, label, annotations in source.annotation_rows:
                    label = label.replace(" ", "_")
                    row_var = self.writer.register_var(source.id, label, "string")
                    for a in annotations:
                        decoder_rows[a] = row_var
                self.annotation_row_vars[source] = decoder_rows
            row_var = self.annotation_row_vars[source][data[0]]
            self.buffered_changes.append((row_var, startsample, True, data[1][0]))
            self.buffered_changes.append((row_var, endsample, False, startsample))

    def stop(self):
        def change_key(change):
            var, samplenum, start, data = change
            return (samplenum, id(var), start)

        last_start = {}
        for var, samplenum, start, data in sorted(self.buffered_changes, key=change_key):
            if not start:
                if data != last_start[var]:
                    continue
                else:
                    data = None
            else:
                last_start[var] = samplenum
            self.writer.change(var, samplenum, data)
        self.writer.close()
