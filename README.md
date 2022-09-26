# Finance360 (TradeTrainer)

A web-based system to learn about about investing. Create an account, sign in, and start trading stocks! Provides real-time market analytics as well.

## Usage
The app uses Flask. Installing the requirements.txt should automatically install the correct version of Flask. Install requirements by running:
```pip install -r requirements.txt```

You will also need to set up an account with IEX, the API I use to collect stock data: 
1. Visit [IEX Cloud](iexcloud.io/cloud-login#/register/) to make an account.
2. Once signed in, click 'API Tokens', copy the appropriate token (use a Sandbox token for experimentation), and store it to a .env file as 'TOKEN'.
3. Create a secret key for your app (not API-related) and place it in the .env file as 'SECRET_KEY'.

The project uses a SQLite3 database to persist data. You may need to install [SQLite3](https://www.tutorialspoint.com/sqlite/sqlite_installation.htm) if you don't have it, and create your own database called finances.db (or using your own nomenclature).

When running the app, please make a new account when signing in for the first time.

To run locally, use:
```flask run```
