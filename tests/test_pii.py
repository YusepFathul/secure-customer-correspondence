from scc.pii import domain_typo, is_valid_nik, mask_email, mask_nik, redact_niks


def test_valid_nik_structure():
    assert is_valid_nik("3273024502850002")      # Bandung, female (45 = 5 + 40), Feb 1985
    assert not is_valid_nik("9973024502850002")  # unknown province
    assert not is_valid_nik("3273021313850002")  # month 13 does not exist
    assert not is_valid_nik("32730245028500")    # too short


def test_masking_keeps_only_edges():
    assert mask_nik("3273024502850002") == "3273********0002"
    assert mask_email("budi.wijaya@yahoo.example") == "b***@yahoo.example"


def test_nik_inside_file_name_is_redacted():
    name = "MATURITY_7700000001_3171010101800001_209901.pdf"
    assert "3171010101800001" not in redact_niks(name)
    assert "7700000001" in redact_niks(name)  # 10-digit policy numbers are left alone


def test_domain_typo_detection():
    assert domain_typo("someone@gmial.com") == "gmail.com"
    assert domain_typo("someone@gmail.com") is None
    assert domain_typo("someone@nusantaralife.example") is None
    assert domain_typo("someone@gmial.example") == "gmail.example"
    assert domain_typo("someone@yahoo.example") is None
