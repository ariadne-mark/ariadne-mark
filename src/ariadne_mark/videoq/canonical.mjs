// Validate a recovered BCH5 word by re-encoding with the pinned upstream codec.
// Codeword validity does not authenticate the source content or issuer.
export function canonicalPacket(layer, raw) {
  if (raw.length !== 100 || !Array.from(raw).every(x => x === 0 || x === 1)) return null;
  const decoded = layer.decode(raw);
  if (!decoded.valid || decoded.schema !== 'BCH_5' || decoded.data.length !== 61) return null;
  const canonical = layer.encode(decoded.data, 'BCH_5');
  let distance = 0;
  for (let i = 0; i < 96; i++) distance += raw[i] !== canonical[i] ? 1 : 0;
  return distance <= 5 ? decoded : null;
}
