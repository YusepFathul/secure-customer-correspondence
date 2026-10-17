from scc.pii import (domain_typo, find_nik_like, is_valid_nik, mask_email, mask_name, mask_nik,
                     mask_street, redact_niks)

# Test values use province code 99, which does not exist, so they can never be a real NIK


def test_nik_structure_rules():
    assert not is_valid_nik("9973024502850002")  # unknown province
    assert not is_valid_nik("3273021313850002")  # month 13 does not exist
    assert not is_valid_nik("32730245028500")    # too short


def test_masking_keeps_only_edges():
    assert mask_nik("9999999999990002") == "9999********0002"
    assert mask_nik("9999********0002") == "9999********0002"  # already masked stays the same
    assert mask_name("Budi Wijaya") == "Budi W*****"
    assert mask_street("Jl. Merdeka") == "Jl. M******"
    assert mask_email("customer.0002@yahoo.example") == "c***@yahoo.example"


def test_nik_inside_file_name_is_found_and_redacted():
    assert find_nik_like("MATURITY_7700000001_NIK9999xxxxxxxx0001_209901.pdf")
    assert find_nik_like("MATURITY_7700000001_9999999999990001_209901.pdf")
    assert not find_nik_like("MATURITY_7700000001_209901.pdf")
    name = "MATURITY_7700000001_9999999999990001_209901.pdf"
    assert "9999999999990001" not in redact_niks(name)
    assert "7700000001" in redact_niks(name)  # 10-digit policy numbers are left alone


def test_domain_typo_detection():
    assert domain_typo("someone@nusantaralife.example") is None
    assert domain_typo("someone@gmial.example") == "gmail.example"
    assert domain_typo("someone@yahoo.example") is None
