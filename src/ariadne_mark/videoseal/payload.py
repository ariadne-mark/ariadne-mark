"""Versioned 256-bit payload: 112 data bits + 140 BCH bits + four zero bits.

Uses the MIT-licensed BCH implementation shipped with pinned TrustMark.
CRC and prefix reject accidental decoding; neither authenticates the issuer.
"""
import threading
import zlib
from ariadne_mark.watermark import valid_token

FORMAT = "ariadne-vs1"
ALGORITHM = "meta.videoseal.1.0.bch20"


class Payload:
    def __init__(self):
        from trustmark.bchecc import BCH
        self.bch = BCH(20, 285)
        if self.bch.get_ecc_bits() != 140:
            raise ValueError("Unexpected BCH implementation")
        self.lock = threading.RLock()

    def encode(self, token):
        if not valid_token(token):
            raise ValueError("Invalid Ariadne token")
        data = b"AM" + bytes.fromhex(token)
        data += zlib.crc32(data).to_bytes(4, "big")
        with self.lock:
            ecc = self.bch.encode(bytearray(data))
        bits = ''.join(f"{b:08b}" for b in data)
        bits += ''.join(f"{b:08b}" for b in ecc)[:140]
        return [int(b) for b in bits + "0000"]

    def decode(self, bits):
        if len(bits) != 256 or any(b not in (0, 1) for b in bits):
            raise ValueError("Expected 256 binary values")
        text = ''.join(str(int(b)) for b in bits)
        data = bytearray(int(text[:112], 2).to_bytes(14, "big"))
        ecc = bytearray(int(text[112:252] + "0" * 20, 2).to_bytes(20, "big"))
        with self.lock:
            errors = self.bch.decode(data, ecc)
            if not 0 <= errors <= 20:
                return None
            if data[:2] != b"AM" or zlib.crc32(data[:10]) != int.from_bytes(data[10:], "big"):
                return None
            token = data[2:10].hex()
            if not valid_token(token):
                return None
            # Re-encoding guards decoder miscorrection and includes padding bits.
            distance = sum(a != b for a, b in zip(bits, self.encode(token)))
            return {"token": token, "corrected_bits": distance} if distance <= 20 else None
