"""Bound explicit AI cases without generating, truncating or changing their values."""


def validate_case_limits(cases, profile):
    """Use existing case-size and logical collection limits for the new preparation mode."""
    settings=profile.executable_verification
    def collections(value):
        if isinstance(value,list):
            if len(value)>settings.max_collection_items:raise ValueError('AI fixture collection exceeds the configured item limit')
            for child in value:collections(child)
        elif isinstance(value,dict):
            for child in value.values():collections(child)
    for case in cases:
        if len(case.model_dump_json())>settings.max_case_chars:raise ValueError('AI fixture exceeds the configured case-size limit')
        collections(case.initial_context)
        collections(case.test_assets.get('inputs',{}))
        collections(case.test_assets.get('resources',{}))
