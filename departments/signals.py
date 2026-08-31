def seed_internal_howtos_after_migrate(**kwargs):
    from .services.internal_howto_seed import seed_finance_internal_howtos

    seed_finance_internal_howtos()
