from pathlib import Path

import pytest

from ..populate_db import PopulateDatabase
from ..populate_db.read_data_files import read_patch_csv, make_combined_dict
from mediabrowser.models import VisionItem

DATABASE = "db_test"


def test_combine_patch_films_list(
    films_txt, patch_csv, expected_patch_filenames, expected_films_filenames
):

    combined_dct = make_combined_dict(films_txt, patch_csv)
    assert set(combined_dct.keys()) == set(expected_patch_filenames) | set(expected_films_filenames)

    for fname in expected_patch_filenames:
        assert len(combined_dct[fname]) > 0

    for fname in expected_films_filenames:
        assert len(combined_dct[fname]) == 0

    patch_dct = make_combined_dict(None, patch_csv)
    assert set(patch_dct.keys()) == set(expected_patch_filenames)

    films_dct = make_combined_dict(films_txt, None)
    assert films_dct == {fname: {} for fname in expected_films_filenames}

    assert make_combined_dict(None, None) == {}


@pytest.mark.django_db(databases=[DATABASE], transaction=True)
def test_populate_db(
    films_txt,
    patch_csv,
    physical_media_csv,
    expected_patch_filenames,
    expected_films_filenames,
    monkeypatch,
):
    print()

    read_patch_csv_orig = read_patch_csv

    def patch_no_disc_index(patch_csv):
        # remove disc indexes, so we can check that they're added from physical media csv
        patch = read_patch_csv_orig(patch_csv)

        for file in patch.keys():
            patch[file].pop("disc_index")

        return patch

    from ..populate_db import read_data_files

    monkeypatch.setattr(read_data_files, "read_patch_csv", patch_no_disc_index)

    pop_db = PopulateDatabase(physical_media=physical_media_csv, quiet=False, database=DATABASE)
    n = pop_db.update(films_txt=films_txt, patch_csv=patch_csv)

    assert n == len(expected_films_filenames) + len(expected_patch_filenames)

    # check that info from physical media csv was applied correctly
    patch = read_patch_csv_orig(patch_csv)
    for file, info in patch.items():
        if info["disc_index"] != "":
            item = VisionItem.objects.using(DATABASE).get(filename=str(file))
            assert (
                item.disc_index == info["disc_index"]
            ), f"{file=}, expected disc index {info['disc_index']}, got {item.disc_index}"
