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


def media_scope(value, *, video):
    """Return promised schemes for this media, independently of input claims.

    Current Q video may additionally use Python-Q reads, but a negative Q video
    scan is not a negative check of the older Python-Q video bit layout.
    ``all`` or an explicit Python-Q-only scope retains that legacy obligation.
    """
    configured = normalize_scope(value)
    if not video:
        return tuple(s for s in configured if s == CURRENT_SCHEMES[0])
    if set(configured) == set(CURRENT_SCHEMES):
        return (CURRENT_SCHEMES[1],)
    return configured


def runtime_warnings(scope):
    """Cheap pinned-model preflight; never download or load inference models."""
    if ALL_SCHEMES[-1] not in normalize_scope(scope):
        return []
    try:
        import importlib.util
        if importlib.util.find_spec('torch') is None:
            raise ImportError('Legacy VideoSeal requires the media runtime')
        from ariadne_mark.videoseal import check_models
        check_models()
    except Exception as exc:
        # This is a warning, never an inference result or an automatic migration.
        return [{'code': 'legacy_decoder_unavailable', 'reason': type(exc).__name__,
                 'message': 'Configured all scope includes legacy VideoSeal, but its pinned model is unavailable. '
                            'Provision it explicitly if legacy marks were issued; narrow to current only after reviewing historical issuance.'}]
    return []
