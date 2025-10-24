import argparse
import yaml
from pathlib import Path
from import_pucks import start_app
from utils.pandas_model import PuckPandasModel


def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        usage="%(prog)s [OPTION] [FILE]...", description="Start the puck importer GUI"
    )

    parser.add_argument(
        "-v", "--version", action="version", version=f"{parser.prog} version 1.0.0"
    )
    parser.add_argument("config", help="yaml file containing the configuration")
    return parser


def main() -> None:
    parser = init_argparse()
    args = parser.parse_args()
    if not args.config:
        print("Please include the yaml file containing the app configuration")
        return
    config_path = Path(args.config)
    if not config_path.exists():
        print(
            f"Configuration file {config_path} does not exist, please provide a valid config path"
        )
        return
    
    try:
        start_app(config_path)
    except Exception as e:
        print(f'Exception occurred: {e}')


if __name__ == "__main__":
    main()



def make_model(excel_file, required_columns_list):
    for sheet_name in excel_file.sheet_names:

        data = excel_file.parse(sheet_name)
        
        if data.empty:
            print('no sheet')
            continue
        # Check if any row besides header row contains "puckname"
        rows = (data.map(lambda x: str(x).lower() == required_columns_list[0])).any(
            axis=1
        )

        required_columns = set(required_columns_list)
        header_correct = required_columns.issubset(
            (
                col.strip().lower()
                for col in data.columns
                if isinstance(col, str)
            )
        )
        print("header_correct {}".format(header_correct))
        if not rows.all() and not header_correct:
            import_offset = data.loc[rows].first_valid_index()
            if isinstance(import_offset, (int, np.integer)):
                data = excel_file.parse(
                    sheet_name=sheet_name, skiprows=import_offset + 1
                )
        data.rename(
            columns={
                col: col.strip().lower()
                for col in data.columns
                if isinstance(col, str)
            },
            inplace=True,
        )
        # Check headers again after offset
        header_correct = required_columns.issubset(
            (
                col.strip().lower()
                for col in data.columns
                if isinstance(col, str)
            )
        )
        if header_correct:
            #HEADER IS CORRECT, PUCKS IMPORTED CORRECTLY, OFF TO VAlIDATING DATA
            model = PuckPandasModel(data)
            model.setPuckList([])
            return model