Automated Member Data Migration and QA System

1. Project Overview

This project involved the development of a Python-based system for automating member data migration and quality assurance. The program reads member records from an Excel workbook, cleans and standardizes the data, removes duplicates, separates records that require manual review, and creates a clean dataset that is ready for migration.

The system also produces an Excel QA report and maintains a log of each execution. Automated tests are included to verify the main cleaning, validation, and reconciliation rules whenever the project is updated.

2. Business Problem

Member information exported from an old system is not always ready to move into a new database. The Excel file may contain inconsistent headings, missing member numbers, repeated records, spelling differences, or two different names under the same member number.

Checking these issues manually is time-consuming and can lead to errors. The project was designed to automate repetitive tasks while directing uncertain records to manual review instead of making unreliable assumptions.

3. Project Objectives

The main objectives of this project were to:

Read the required member fields from an Excel workbook

Check the overall quality of the source data

Clean unnecessary spaces and standardize supported gender values

Validate member numbers and required names

Detect duplicate and conflicting records

Keep valid records separate from records that need manual review

Assign new sequential member numbers to the cleaned data

Create an Excel QA report

Record useful run information without logging private member details

Test the main functions automatically

Provide an optional SQL Server loading feature

Use synthetic data for the public demonstration

4. Technologies Used

The following technologies were used:

Python 3.13

pandas

openpyxl

pytest

SQLAlchemy and pyodbc

python-dotenv

Python standard libraries such as pathlib, logging, argparse, datetime, re, hashlib, and dataclasses

5. Project Structure

member-data-automation/
├── data/
│   ├── private/
│   └── sample/
│       └── synthetic_member_data.xlsx
├── output/
│   ├── private/
│   └── sample/
│       ├── cleaned_members_sample.xlsx
│       ├── manual_review_sample.xlsx
│       └── qa_report_sample.xlsx
├── src/
│   ├── config.py
│   ├── extract.py
│   ├── transform.py
│   ├── validate.py
│   ├── report.py
│   ├── sample_generator.py
│   └── database.py
├── tests/
│   ├── test_transform.py
│   ├── test_validation.py
│   └── test_reconciliation.py
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md

Each Python file has a separate purpose. For example, extraction, transformation, validation, reporting, and database loading are kept in different files. This makes the code easier to understand, test, and update.

6. ETL and QA Process

flowchart TD
    A["Excel source"] --> B["Extract required fields"]
    B --> C["Clean and standardize"]
    C --> D{"Validate records"}
    D -->|Valid| E["Clean migration file"]
    D -->|Problem found| F["Manual-review file"]
    E --> G["QA report"]
    F --> G
    G --> H["Optional SQL Server load"]

The program follows these steps:

Extract: It checks the workbook sheets and selects the sheet that contains the required columns. It then reads the member number, English name, Nepali name, and gender.

Clean: It removes unnecessary spaces, checks member-number formats, standardizes supported gender values, and preserves Nepali Unicode text.

Validate: Records with missing or invalid required information are moved to manual review.

Handle duplicates: Exact duplicate records are removed. Records with the same member number and name are combined by keeping the most complete version. Conflicting names under the same number are sent for manual review.

Create outputs: Valid records receive new sequential IDs and are written to a cleaned Excel file.

Produce the QA report: The program creates a report showing counts, missing values, duplicate information, gender distribution, validation results, and run details.

Load to SQL Server: This is optional and disabled unless the required safety settings are enabled.

7. Data-Cleaning Rules

The following rules were applied during data cleaning:

English names are trimmed, and repeated spaces are reduced to one space.

Original punctuation and capitalization in names are kept.

Nepali names remain in Unicode and are not translated or transliterated.

A Nepali name can be blank because it is not a required field.

Member numbers must be whole numbers.

Missing, non-numeric, or fractional member numbers are treated as invalid.

Text member numbers with leading zeros are recorded for audit purposes.

Common gender values such as Male, male, M, Female, female, and F are standardized.

Unsupported gender values become null, while the original value remains available in the audit information.

The program never guesses gender from a person's name.

8. Duplicate-Handling Rules

Duplicates are handled according to the type of repetition:

If two rows are exactly the same, one is kept and the extra row is removed.

If the member number and name are the same but one row contains more complete information, the more complete record is kept.

If the same member number appears with different names, all related rows are moved to manual review.

Alphabetical order is not used to select between conflicting names because it could retain an incorrect record. These cases must be reviewed manually.

9. Validation and Reconciliation

The program runs 15 validation checks during every execution. These checks include:

Correct output columns

Unique member numbers

Sequential member numbers without gaps

Valid gender values

Presence of the required output files

Correct reconciliation totals

Matching source-file checksums before and after processing

The reconciliation formula is:

Raw records = Cleaned records + Manual-review records + Duplicates removed

The checksum check confirms that the program reads the source workbook without changing it.

10. Installation

The project can be installed with the following commands:

git clone <your-repository-url>
cd member-data-automation
python -m venv .venv

For Windows PowerShell:

.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

11. Running the Program

To create the synthetic demonstration dataset:

python main.py --generate-sample

To run the automation using the synthetic data:

python main.py --input "data/sample/synthetic_member_data.xlsx" --mode sample

To process a private workbook:

python main.py --input "data/private/source_member_data.xlsx" --mode private

Private data should never be uploaded to the public repository.

12. Automated Testing

The test suite was executed with:

python -m pytest -v

The project contains tests for data transformation, validation, duplicate handling, reconciliation, Unicode preservation, and file-integrity checks. All 54 tests passed successfully.

The tests use fictional names and numbers. No real member data is included.

13. Output Files

File

Purpose

cleaned_members.xlsx

Contains valid, cleaned records that are ready for migration

manual_review.xlsx

Contains records that need a person to check them

qa_report.xlsx

Contains the QA summary, missing values, duplicate details, gender totals, validation results, and run information

automation.log

Records general execution information without storing full member records

14. SQL Server Option

The SQL Server loader is available in src/database.py, but it is disabled by default. Loading data requires both:

The --load-sql option in the command, and

ALLOW_SQL_LOAD=true in the environment settings.

The loader validates the cleaned data before inserting it. It uses a transaction, rolls back if an error occurs, and checks the number of inserted rows afterward. It does not automatically drop or truncate tables, and database credentials are not written directly into the code.

This feature should first be tested with a development database:

python main.py --input "data/sample/synthetic_member_data.xlsx" --mode sample --load-sql

15. Privacy and Confidentiality

The original workbook used for the project contained confidential member information. For this reason, the real workbook, private outputs, environment file, and log files are excluded from Git using .gitignore.

The public GitHub repository contains only the source code, tests, documentation, and fictional data generated by the sample-data script. The real organization name and original file name are not included.

16. Synthetic Data

The file src/sample_generator.py creates 38 fictional member records for demonstration and testing. The sample includes:

Extra spaces

Missing values

Different gender formats

Unsupported gender values

Exact duplicates

Repeated member numbers

Conflicting names

Invalid member numbers

These examples allow the main rules to be tested without exposing any real information.

17. Skills Demonstrated

The project demonstrates the following skills:

Designing an ETL workflow

Organizing Python code into separate modules

Cleaning text and numeric data

Preserving Nepali Unicode characters

Handling duplicates in a consistent way

Separating uncertain records for manual review

Creating reconciliation and validation checks

Writing automated tests with pytest

Creating formatted Excel reports

Connecting Python to SQL Server safely

Using Git and GitHub for version control

Protecting private information

18. Sample Results

The synthetic dataset produced the following results:

Metric

Result

Raw records

38

Cleaned records

30

Manual-review records

6

Duplicate records removed

2

Reconciliation

38 = 30 + 6 + 2

Overall QA status

PASSED

These numbers are from the fictional demonstration data and do not represent the real organization or its members.

19. Challenges and Problem Solving

During execution, Windows Application Control blocked a Pandas DLL under Python 3.14. The issue was resolved by installing Python 3.13.14, creating a new virtual environment, reinstalling the project requirements, and testing the imports again. Pandas then loaded correctly.

After the environment was corrected, the synthetic dataset was generated and the complete automation was executed successfully. The QA status passed, and all 54 automated tests were completed successfully before the project was pushed to GitHub.

20. Future Improvements

Possible future improvements include:

Moving header-matching rules into a separate configuration file

Adding optional fuzzy matching for similar names, with human approval

Building a simple interface for reviewing rejected records

Improving bulk loading for larger Excel files

Adding GitHub Actions so the tests run automatically after every push

21. Conclusion

This project demonstrates that data migration involves more than transferring information from one system to another. Source data must first be assessed, cleaned, validated, and reconciled.

The final program completed the sample migration process successfully, produced separate cleaned and manual-review files, passed all QA checks, and passed all 54 automated tests. Private data is also kept separate from the public source code. Overall, the project demonstrates practical application of Python automation, QA testing, Excel processing, SQL Server integration, and version control.

22. License

This project uses the MIT License. The full license is available in the LICENSE file.
