"""BCH5 acceptance guard for pinned, pre-fix upstream decoders.

Re-encoding the recovered payload must put it within the five-bit correction
radius of the received 96-bit data+parity word. Schema bits are not protected
by that BCH code. This validates a codeword, not provenance or authenticity.
See Adobe TrustMark's November 2026 canonical BCH validation fix.
"""


class CanonicalBCH5:
    """Instance-local adapter; never modifies the installed upstream package."""
    def __init__(self, layer):
        self.layer = layer

    def __getattr__(self, name):
        return getattr(self.layer, name)

    def decode_bitstream(self, packets, MODE='binary'):
        if MODE != 'binary':
            raise ValueError('SDK canonical decoder requires binary mode')
        rows = self.layer.decode_bitstream(packets, MODE=MODE)
        if len(rows) != len(packets):
            raise ValueError('Incomplete BCH decode')
        result = []
        for raw, (bits, present, schema) in zip(packets, rows):
            valid = bool(present and schema == 1 and len(bits) == 61
                         and set(bits) <= {'0', '1'} and len(raw) == 100
                         and all(x in (0, 1) for x in raw))
            if valid:
                canonical = self.layer.encode_binary([bits])[0]
                valid = (len(canonical) == 100
                         and sum(int(a) != int(b) for a, b in zip(raw[:96], canonical[:96])) <= 5)
            result.append((bits, valid, schema))
        return result
