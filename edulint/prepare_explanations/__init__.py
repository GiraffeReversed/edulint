from pylint_data import extract_from_pylint
from thonny_data import extract_from_edulint


def main():
    extract_from_pylint.process_from_stored_data()
    extract_from_edulint.process_from_stored_data()


if __name__ == "__main__":
    main()

