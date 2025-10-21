from datetime import date

from app.domain.numbering import NumberingConfig, NumberingService


def test_numbering_sequences_reset_annually(tmp_path):
    state = {"numbering": {}}

    def load_config():
        return state

    def save_config(cfg):
        state.update(cfg)

    service = NumberingService(load_config, save_config)
    number1 = service.next_invoice_number("OST", "OST-", date(2024, 1, 10))
    number2 = service.next_invoice_number("OST", "OST-", date(2024, 5, 10))
    number3 = service.next_invoice_number("OST", "OST-", date(2025, 1, 10))

    assert number1 == "OST-2024-0001"
    assert number2 == "OST-2024-0002"
    assert number3 == "OST-2025-0001"


def test_numbering_without_reset(tmp_path):
    state = {"numbering": {}}

    def load_config():
        return state

    def save_config(cfg):
        state.update(cfg)

    service = NumberingService(load_config, save_config)
    cfg = NumberingConfig(reset_annually=False)
    number1 = service.next_invoice_number("DRL", "DRL-", date(2024, 1, 1), cfg)
    number2 = service.next_invoice_number("DRL", "DRL-", date(2025, 1, 1), cfg)

    assert number1 == "DRL-0001"
    assert number2 == "DRL-0002"
