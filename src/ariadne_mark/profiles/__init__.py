"""Offline, versioned requirement planning. Declarations never become certification."""
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
from importlib.resources import files
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

CATALOG = json.loads(files(__package__).joinpath('catalog.json').read_text())


def template():
    return {
        'schema_version': 1, 'jurisdictions': ['EU', 'US-CA'], 'role': 'unknown',
        'media_kinds': ['image', 'video'], 'publisher': '', 'system': {'name': '', 'version': ''},
        'context': {'eu_in_scope': None, 'eu_first_placed_on_market': None,
                    'deepfake': None, 'creative_work': None, 'eu_exception': 'none',
                    'ca_public_access': None, 'ca_produces_system': None, 'ca_exception': 'none',
                    'licenses_system_to_third_parties': None},
        'sdk': {'audio_kind': 'unknown', 'video_profile': 'economy_5s', 'video_profile_reason': None},
        'deployment': {'disclosure': 'none', 'accessibility_review': False,
                       'verifier_url': None, 'verifier_free': None, 'verifier_upload': None,
                       'verifier_api': None, 'verifier_url_submission': None, 'verifier_provider': 'unknown',
                       'verifier_link_in_product': None, 'feedback_url': None,
                       'privacy_review': False, 'verifier_public_sources_reviewed': None, 'durability_evidence': None,
                       'interoperability_evidence': None},
    }


def _object(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f'{name}: missing or unknown fields; expected {sorted(expected)}')


def _enum(value, choices, name):
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f'{name}: expected one of {sorted(choices)}')


def _text(value, name, nullable=False, empty=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or len(value) > 512 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f'{name}: expected plain text, at most 512 characters')
    if not empty and not value.strip():
        raise ValueError(f'{name}: empty value')


def parse_date(value, name):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f'{name}: use YYYY-MM-DD')
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError(f'{name}: use YYYY-MM-DD')
    return result


def validate(config):
    default = template()
    _object(config, default, 'config')
    config = deepcopy(config)
    # Older files are parsed, but a missing video-mode choice blocks profiled video export.
    if isinstance(config['sdk'], dict):
        config['sdk'].setdefault('video_profile', None)
        config['sdk'].setdefault('video_profile_reason', None)
    if isinstance(config.get('deployment'), dict):
        config['deployment'].setdefault('verifier_public_sources_reviewed', None)
    for section in ('context', 'sdk', 'deployment', 'system'):
        _object(config[section], default[section], section)
    if type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise ValueError('Unsupported schema_version')
    for key, allowed in [('jurisdictions', {'EU', 'US-CA'}), ('media_kinds', {'image', 'video', 'audio', 'text'})]:
        values = config[key]
        if not isinstance(values, list) or not values or any(not isinstance(v, str) for v in values) or len(set(values)) != len(values) or set(values) - allowed:
            raise ValueError(f'{key}: expected unique values from {sorted(allowed)}')
    _enum(config['role'], {'provider', 'deployer', 'both', 'unknown'}, 'role')
    _text(config['publisher'], 'publisher', empty=True)
    for key in ('name', 'version'):
        _text(config['system'][key], 'system.' + key, empty=True)
    ctx, dep = config['context'], config['deployment']
    for key in ('eu_in_scope', 'deepfake', 'creative_work', 'ca_public_access', 'ca_produces_system', 'licenses_system_to_third_parties'):
        if ctx[key] is not None and type(ctx[key]) is not bool:
            raise ValueError(f'context.{key}: expected true, false or null')
    if ctx['eu_first_placed_on_market'] is not None:
        parse_date(ctx['eu_first_placed_on_market'], 'eu_first_placed_on_market')
    _enum(ctx['eu_exception'], {'none', 'standard_editing', 'law_enforcement', 'other', 'unknown'}, 'eu_exception')
    _enum(ctx['ca_exception'], {'none', 'minor_modification', 'assistive_technology', 'non_user_generated_videogames', 'other', 'unknown'}, 'ca_exception')
    _enum(config['sdk']['audio_kind'], {'none', 'original', 'synthetic', 'unknown'}, 'audio_kind')
    from ariadne_mark.video.policy import validate_profile
    if config['sdk']['video_profile'] is not None:
        validate_profile(config['sdk']['video_profile'])
    _text(config['sdk']['video_profile_reason'], 'sdk.video_profile_reason', nullable=True)
    _enum(dep['disclosure'], {'none', 'in_app', 'baked_in', 'both'}, 'disclosure')
    _enum(dep['verifier_provider'], {'own', 'third_party', 'unknown'}, 'verifier_provider')
    for key in ('accessibility_review', 'privacy_review'):
        if type(dep[key]) is not bool:
            raise ValueError(f'{key}: expected true or false')
    for key in ('verifier_free', 'verifier_upload', 'verifier_api', 'verifier_url_submission', 'verifier_link_in_product', 'verifier_public_sources_reviewed'):
        if dep[key] is not None and type(dep[key]) is not bool:
            raise ValueError(f'{key}: expected true, false or null')
    for key in ('verifier_url', 'feedback_url', 'durability_evidence', 'interoperability_evidence'):
        _text(dep[key], key, nullable=True)
    return deepcopy(config)


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate config key: {key}')
            result[key] = value
        return result
    with Path(path).open('rb') as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError('Profile configuration exceeds 64 KiB')
    return validate(json.loads(raw, object_pairs_hook=unique))


def _public_https(value):
    if not value:
        return False
    try:
        url = urlsplit(value)
        host = url.hostname or ''
        if url.scheme != 'https' or not host or url.username or url.password or not url.port in (None, 443):
            return False
        if host.lower().rstrip('.') == 'localhost' or host.lower().rstrip('.').endswith(('.localhost', '.local')):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            # Syntax only. Never fetch operator URLs or claim reachability.
            host = host.encode('idna').decode('ascii').rstrip('.')
            return len(host) <= 253 and '.' in host and all(
                re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                for label in host.split('.'))
    except (ValueError, UnicodeError):
        return False


def evaluate(config, *, as_of=None):
    config = validate(config)
    today = as_of or datetime.now(timezone.utc).date()
    if type(today) is not date:
        raise ValueError('as_of must be a date')
    ctx, dep = config['context'], config['deployment']
    findings, requirements, applicability = [], [], {}
    def finding(code, level, message, source='SDK'):
        findings.append({'id': code, 'level': level, 'message': message, 'source_id': source})
    def requirement(code, state, message, source, provision, owner='operator'):
        requirements.append({'id': code, 'state': state, 'message': message,
                             'source_id': source, 'provision': provision, 'owner': owner})
    def declaration(code, value, message, source, provision):
        requirement(code, 'declared_not_verified' if value else 'action_required', message, source, provision)
    reviewed = parse_date(CATALOG['reviewed_on'], 'reviewed_on')
    if (today - reviewed).days > CATALOG['review_interval_days']:
        finding('source_refresh', 'review', 'Source snapshot is older than the SDK 30-day review interval; recheck operative law.', 'SDK')
    for field, value in [('publisher', config['publisher']), ('system.name', config['system']['name']), ('system.version', config['system']['version'])]:
        if not value.strip():
            finding('missing_' + field, 'error', f'Fill {field} with truthful public product information.')
    if set(config['media_kinds']) - {'image', 'video'}:
        finding('unsupported_media', 'error', 'This SDK profile exports images/video only; audio/text require a separate solution.')
    if 'video' in config['media_kinds'] and config['sdk']['audio_kind'] in {'synthetic', 'unknown'}:
        finding('audio_scope', 'error' if config['sdk']['audio_kind'] == 'synthetic' else 'review', 'Audio is retained but not independently watermarked. Resolve unknown/synthetic audio outside the visual profile.')
    if 'video' in config['media_kinds'] and config['sdk']['video_profile'] is None:
        finding('video_profile_required', 'error', 'Explicitly choose economy_5s, economy_2s or resilient for profiled video export.')
    if 'video' in config['media_kinds'] and not config['sdk']['video_profile_reason']:
        finding('video_profile_reason', 'review', 'Record why the selected preset fits compute cost, delivery transformations and durability evidence. This is not a legal determination.')
    if 'video' in config['media_kinds'] and (config['sdk']['video_profile'] or '').startswith('economy_'):
        finding('economy_durability_review', 'review',
                'Economy is a cost preset, not a statutory marking-frequency minimum. A documented known-window frame-replacement stress removed sparse marks. Review delivery/adversarial durability and detection evidence for your use case; passing ordinary transforms does not certify EU/CA sufficiency.')
    if config['role'] == 'unknown' and 'EU' in config['jurisdictions']:
        finding('eu_role', 'review', 'Determine whether the product is a provider, deployer, or both.', 'EU-50')

    if 'EU' in config['jurisdictions']:
        scope = ctx['eu_in_scope']
        start = date(2026, 8, 2)
        scope_state = 'not_in_scope_declared' if scope is False else 'review_required' if scope is None else 'in_scope_declared'
        applicability['EU'] = {'scope': scope_state}
        if scope is None:
            finding('eu_scope', 'review', 'Assess EU territorial scope, including outputs used in the EU; company location alone is insufficient.', 'EU-50')
        if scope is not False:
            provider = config['role'] in {'provider', 'both', 'unknown'}
            deployer = config['role'] in {'deployer', 'both', 'unknown'}
            if provider:
                launched = parse_date(ctx['eu_first_placed_on_market'], 'eu_first_placed_on_market') if ctx['eu_first_placed_on_market'] else None
                deadline = date(2026, 12, 2) if launched and launched < start else start
                status = 'not_yet_applicable' if today < deadline else 'applies_to_declared_scenario'
                if launched is None and start <= today < date(2026, 12, 2):
                    status = 'review_required'
                    finding('eu_transition', 'review', 'Provide first market-placement date to distinguish 2 August from 2 December 2026 provider-marking dates.', 'EU-TIMING')
                exception = ctx['eu_exception']
                if exception != 'none':
                    status = 'exception_requires_review'
                    finding('eu_exception', 'review', f'Claimed exception ({exception}) needs a factual/legal assessment; marking is not automatically disabled.', 'EU-50')
                applicability['EU']['provider_marking'] = {'state': status, 'effective_on': deadline.isoformat() if launched or not (start <= today < date(2026, 12, 2)) else None}
                if today >= start:
                    requirement('eu_machine_mark', 'partial_measure', 'SDK writes a recoverable ID and signed C2PA; persistence, interoperability and actual product coverage require assessment.', 'EU-50', '50(2)', 'sdk')
                    declaration('eu_robustness', dep['durability_evidence'], 'Evaluate reliability and robustness on the actual product pipeline; a report reference is not a passing assessment.', 'EU-50', '50(2)')
                    declaration('eu_interoperability', dep['interoperability_evidence'], 'Test interoperability with intended consumers and document feasibility/state-of-art considerations.', 'EU-50', '50(2)')
                    requirement('eu_code_route', 'review_required', 'Choose and assess the voluntary Code of Practice route or substantiate alternative measures. Full code adherence is not evaluated here.', 'EU-CODE', 'provider measures')
                    requirement('eu_code_interoperability', 'review_required', 'If relying on the voluntary Code, assess Measure 3.4(c): signatories implement an interoperable detection access/signpost solution by 2027-02-02. This SDK does not implement universal resolver discovery.', 'EU-CODE', '3.4(c)')
            if deployer:
                if today < start:
                    applicability['EU']['deployer_disclosure'] = {'state': 'not_yet_applicable', 'effective_on': start.isoformat()}
                elif ctx['deepfake'] is False:
                    applicability['EU']['deployer_disclosure'] = {'state': 'not_triggered_by_declared_visual_scenario'}
                else:
                    applicability['EU']['deployer_disclosure'] = {'state': 'applies_to_declared_scenario' if ctx['deepfake'] is True else 'review_required'}
                    if ctx['deepfake'] is None:
                        finding('deepfake_assessment', 'review', 'Assess whether the exported content constitutes a deepfake; the SDK does not classify this automatically.', 'EU-50')
                    declaration('eu_disclosure', dep['disclosure'] != 'none', 'Provide understandable disclosure by first exposure. Machine-readable marks alone do not fulfil this user-facing obligation.', 'EU-50', '50(4)-(5)')
                    declaration('eu_accessibility', dep['accessibility_review'], 'Review placement and accessibility. A baked-in label alone does not establish accessibility.', 'EU-50', '50(5)')
                    if ctx['creative_work'] is not False:
                        requirement('eu_creative_context', 'review_required', 'Artistic/fictional content may use an appropriate non-disruptive disclosure; this is not an automatic exemption.', 'EU-50', '50(4)')
            requirement('eu_other_duties', 'review_required', 'Check other applicable duties, including direct AI interaction under 50(1); this profile covers visual-content marking/disclosure only.', 'EU-50', '50(1), 50(6)')

    if 'US-CA' in config['jurisdictions']:
        ca_state = 'applies_to_declared_scenario'
        if today < date(2026, 9, 30):
            ca_state = 'historical_version_not_supported'
            finding('ca_historical_version', 'review', 'This profile encodes the 30 September 2026 amendment, not the earlier threshold/manifest-disclosure rules.', 'CA-22757')
        elif ctx['ca_public_access'] is False or ctx['ca_produces_system'] is False:
            ca_state = 'provider_duties_not_triggered_by_declaration'
        elif ctx['ca_public_access'] is None or ctx['ca_produces_system'] is None:
            ca_state = 'review_required'
            finding('ca_scope', 'review', 'Determine whether you produce a GenAI system publicly accessible in California. No monthly-user threshold is applied.', 'CA-22757')
        exception = ctx['ca_exception']
        if exception != 'none':
            ca_state = 'exception_requires_review'
            finding('ca_exception', 'review', f'Claimed exception ({exception}) requires review; it does not automatically disable technical measures.', 'CA-22757')
            if exception == 'assistive_technology' and today >= date(2029, 1, 1):
                finding('ca_assistive_expired', 'review', 'The statutory temporary assistive-technology exclusion ended on 2029-01-01.', 'CA-22757')
        applicability['US-CA'] = {'provider_duties': ca_state, 'effective_on': '2026-08-02', 'profile_revision_effective_on': '2026-09-30', 'monthly_user_threshold': None}
        if ca_state != 'provider_duties_not_triggered_by_declaration' and today >= date(2026, 9, 30):
            requirement('ca_latent_metadata', 'partial_measure', 'C2PA records the disclosure fields; the watermark contains only an ID. After metadata loss, fields need the operator’s persistent registry and deployed /records resolver. Cross-provider discovery, deployment permanence and authenticated linkage of edited copies are not established.', 'CA-22757', '22757.3(a)(1)', 'sdk')
            requirement('ca_no_mandatory_overlay', 'information', 'The amended provider duties do not require offering a manifest/visible disclosure. Other laws or product contexts may still require one.', 'CA-22757', 'SB 1000 section 4')
            declaration('ca_verifier_public', _public_https(dep['verifier_url']), 'Publish a working verifier; HTTPS URL syntax is checked, reachability is not.', 'CA-22757', '22757.2(a)(4)')
            declaration('ca_verifier_free', dep['verifier_free'] is True, 'Verification must be free to the user.', 'CA-22757', '22757.2(a)')
            declaration('ca_upload', dep['verifier_upload'] is True or dep['verifier_url_submission'] is True, 'Offer upload or URL submission. This SDK supplies upload; remote URL fetching is not required when upload is available.', 'CA-22757', '22757.2(a)(5)')
            declaration('ca_api', dep['verifier_api'] is True, 'Provide programmatic access; deploy and test the bundled verification API.', 'CA-22757', '22757.2(a)(6)')
            declaration('ca_public_provenance', dep['verifier_public_sources_reviewed'] is True,
                        'Configure --public-sources for reviewed provider/system fields and issuer trust; test that your public verifier displays your system provenance without exposing PII. Defaults withhold unreviewed provenance. This declaration does not inspect the deployment.',
                        'CA-22757', '22757.2(a)(2)')
            declaration('ca_feedback', _public_https(dep['feedback_url']), 'Provide a working feedback route and use relevant feedback to improve verification.', 'CA-22757', '22757.2(b)')
            declaration('ca_privacy', dep['privacy_review'], 'Review necessary data processing, output PII controls, retention, proxy logs and access requirements. SDK defaults alone do not verify the deployment.', 'CA-22757', '22757.2(a), (c)-(d)')
            declaration('ca_robustness', dep['durability_evidence'], 'Evaluate removal/tampering resistance and content-to-record recovery; a short benchmark does not qualify statutory permanence.', 'CA-22757', '22757.3(a)(2)-(4)')
            declaration('ca_interoperability', dep['interoperability_evidence'], 'Validate interoperability and verifier compatibility, including metadata-loss cases.', 'CA-22757', '22757.3(a)(3)-(4)')
            if dep['verifier_provider'] != 'own':
                declaration('ca_third_party_verifier', dep['verifier_provider'] == 'third_party' and dep['verifier_link_in_product'] is True, 'A third-party verifier must meet the section, support your marks, and be clearly accessible through your product UI.', 'CA-22757', '22757.2(e)')
            if today >= date(2029, 1, 1):
                finding('ca_2029_metadata', 'error', '2029 assistive-technology metadata is not represented by this SDK schema; update the profile and schema.', 'CA-22757')
        if ctx['licenses_system_to_third_parties'] is not False:
            requirement('ca_licensing', 'review_required', 'Assess third-party licensing duties, the 72-hour remediation/revocation and 96-hour notice workflows, and Attorney General reporting under 22757.3(b). These are not implemented by a marking library.', 'CA-22757', '22757.3(b)')
        requirement('ca_other_roles', 'review_required', 'Hosting-platform, large-platform and capture-device obligations are outside this covered-provider profile.', 'CA-22757', 'chapter 25 scope')

    errors = [x for x in findings if x['level'] == 'error']
    open_items = [x for x in requirements if x['state'] in {'action_required', 'review_required', 'partial_measure'}]
    needs_action = any(x['state'] == 'action_required' for x in open_items)
    needs_review = bool(open_items or any(x['level'] == 'review' for x in findings))
    options = {'watermark': True, 'c2pa': True, 'image_engine': 'TrustMark Q/BCH-5',
               'video_engine': 'TrustMark Q Economy/Resilient; legacy Fast and VideoSeal compatibility',
               'video_profile': config['sdk']['video_profile'], 'video_profile_reason': config['sdk']['video_profile_reason'], 'visible': dep['disclosure'] in {'baked_in', 'both'},
               'audio_kind': config['sdk']['audio_kind'], 'configuration_source': 'SDK implementation choices'}
    return {'schema_version': 1, 'profile_version': CATALOG['version'], 'evaluated_on': today.isoformat(),
            'sources_reviewed_on': CATALOG['reviewed_on'],
            'configuration_sha256': hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
            'configuration_status': 'invalid' if errors else 'valid',
            'assessment_status': 'action_required' if errors or needs_action else 'review_required' if needs_review else 'configuration_reviewed',
            'legal_determination': 'not_performed', 'declaration_verification': 'not_performed',
            'export_supported': not errors, 'applicability': applicability, 'sdk_options': options,
            'findings': findings, 'requirements': requirements,
            'sources': {key: deepcopy(value) for key, value in CATALOG['sources'].items()}}


def export_settings(config, record):
    """Validate a concrete SDK export against its product configuration."""
    report = evaluate(config)
    if not report['export_supported']:
        raise ValueError('Profile configuration cannot export: ' + '; '.join(x['message'] for x in report['findings'] if x['level'] == 'error'))
    if record.media_kind.value not in config['media_kinds']:
        raise ValueError('Media kind is not included in the selected profile')
    if record.publisher != config['publisher'] or record.system.name != config['system']['name'] or record.system.version != config['system']['version']:
        raise ValueError('Record publisher/system does not match the selected profile')
    if record.media_kind.value == 'video' and config['sdk']['audio_kind'] == 'synthetic':
        raise ValueError('Profiled export does not cover independent synthetic-audio marking; use a separate audio solution')
    return report
