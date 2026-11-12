"""Operator-declared detection scope. Exclusion never means an unmarked file."""
CURRENT_SCHEMES = ('adobe.trustmark.Q.bch5', 'adobe.trustmark.Q.variax-bch5')
ALL_SCHEMES = CURRENT_SCHEMES + ('meta.videoseal.1.0.bch20',)


def normalize_scope(value):
    if isinstance(value, str):
        if value == 'all':
            return ALL_SCHEMES
        if value == 'current':
            return CURRENT_SCHEMES
        raise ValueError('verification_scope must be all, current or a nonempty list of supported schemes')
    if (not isinstance(value, (list, tuple)) or not value
            or any(not isinstance(s, str) or s not in ALL_SCHEMES for s in value)
            or len(set(value)) != len(value)):
        raise ValueError('Invalid operator verification scope')
    return tuple(value)
