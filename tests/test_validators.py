# tests/test_validators.py
from src.core.validators import valida_piva, valida_importo, valida_data


def test_piva_eni_valida():
    assert valida_piva("00743110157")[0] is True

def test_piva_con_prefisso_e_spazi():
    assert valida_piva("IT 00743110157")[0] is True

def test_piva_check_digit_errato():
    ok, err = valida_piva("00743110158")
    assert ok is False
    assert "check digit" in err

def test_piva_lettera_al_posto_di_zero():
    assert valida_piva("0074311015O")[0] is False

def test_piva_vuota():
    assert valida_piva("")[0] is False


def test_importo_italiano():
    assert valida_importo("1.234,56")[0] is True

def test_importo_migliaia_senza_decimali():
    # Il caso che ammazzava float(): "1.234" = milleduecentotrentaquattro
    assert valida_importo("1.234")[0] is True

def test_importo_con_euro():
    assert valida_importo("€ 1.234,56")[0] is True

def test_importo_nan():
    assert valida_importo("NaN")[0] is False

def test_importo_negativo():
    assert valida_importo("-100,00")[0] is False


def test_data_slash():
    assert valida_data("15/07/2026")[0] is True

def test_data_iso():
    assert valida_data("2026-07-15")[0] is True

def test_data_inesistente():
    assert valida_data("32/13/2026")[0] is False