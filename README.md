# Growth Tracker Backend

## Overview
This project is designed to track user growth activities through various metrics such as academic performance, physical exercise, and mental well-being. The backend processes user data from a CSV file, generates reports, and creates visualizations to help users understand their progress.

## Project Structure
```
growth_tracker
├── main.py
├── data_processing
│   ├── __init__.py
│   ├── analyze_csv.py
│   ├── csv_to_txt.py
│   └── weekly_report.py
├── reports
│   ├── __init__.py
│   └── individual_reports.py
├── form_data
│   └── growth_data.csv
├── data
│   └── individual_images
├── requirements.txt
├── README.md
└── user_config.json
```

## Files and Directories

- **main.py**: Entry point for the backend application. Connects various modules and manages data processing and report generation.
  
- **data_processing/**: Contains scripts for loading, validating, and processing CSV data.
  - **analyze_csv.py**: Functions for data validation, cleaning, and user summary generation.
  - **csv_to_txt.py**: Converts CSV data into individual text files for each user.
  - **weekly_report.py**: Generates weekly reports and visualizations.

- **reports/**: Contains scripts for generating individual user reports.
  - **individual_reports.py**: Creates trend plots and compiles user data into PDF reports.

- **form_data/**: Directory containing the input CSV file with user growth tracking data.
  - **growth_data.csv**: The main data source for the application.

- **data/**: Directory for storing generated images for individual user reports.
  - **individual_images/**: Contains images related to user reports.

- **requirements.txt**: Lists the dependencies required for the project.

- **user_config.json**: Stores user-specific configurations for report generation.

## Usage
1. **Setup**: Install the required dependencies listed in `requirements.txt` using pip.
2. **Data Input**: Ensure the `growth_data.csv` file is populated with user data in the `form_data` directory.
3. **Run the Application**: Execute `main.py` to process the data and generate reports.
4. **View Reports**: Check the `data/individual_images` directory for generated images and the `reports` directory for individual user reports.

## Next Steps
- Implement the `main.py` file to orchestrate the execution of the modules.
- Consider adding a web framework to connect the backend with a frontend interface.
- Explore additional features such as user authentication and data visualization enhancements.