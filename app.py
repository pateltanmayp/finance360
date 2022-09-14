from ast import Num
from flask import Flask, redirect, render_template, request, session, flash
import pandas as pd
import sqlite3
import os
import requests

# Create app object and set secret key
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# Connect to local database (not in source control)
db = sqlite3.connect('finances.db', check_same_thread=False)

# Base URL used for production, sandbox URL used otherwise
base_url = 'https://cloud.iexapis.com/v1'
sandbox_url = 'https://sandbox.iexapis.com/stable'

def lookup(code):
    '''
    Lookup a stock and return it's company name and latest price

    code:
        Stock symbol
    '''
    resp = requests.get(sandbox_url+'/stock/'+code+'/quote?token=' + os.environ.get("TOKEN"))
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        return None, None
    resp = resp.json()
    return resp['companyName'], resp['latestPrice']

def get_history(code):
    '''
    Modified version of lookup function to return stock's history as opposed to instantaneous data

    code:
        Stock symbol
    '''
    resp = requests.get(sandbox_url+'/stock/'+code+'/chart?token='+'Tsk_20d966bc98664b2bb99268d28e24f63e')
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        return None, None
    return pd.DataFrame(resp.json())

@app.route("/")
def index():
    try:
        rows = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchall()
    except KeyError:
        rows = None
    
    if rows == None or len(rows) > 0:
        return render_template("index.html")
    return render_template("index.html", fname = rows[0][1])

@app.route("/login", methods=['GET', 'POST'])
def login():
    session.clear()

    # Handle login requests, with error handling (no email, no password, unregistered user)
    if request.method == "POST":
        if not request.form.get("email"):
            flash("Please provide email address.")
            return render_template("login.html")
        elif not request.form.get("password"):
            flash("Please enter your password.")
            return render_template("login.html")
        
        rows = db.execute("SELECT * FROM users WHERE email = ? and password = ? ", (request.form.get("email"), request.form.get("password"))).fetchall()
        if len(rows) != 1:
            flash("You're not registered!")
            return render_template("login.html")

        # Create a new session that will persist until the user logs out
        session["user_id"] = rows[0][0]
        return redirect("/home")

    # Render template if request is GET
    if request.method == "GET":
        return render_template("login.html")

@app.route("/signup", methods=['GET', 'POST'])
def signup():
    session.clear()

    # Handle registration requests with error handling (no email, no password, already registered user)
    if request.method == "POST":
        if not request.form.get("email"):
            flash("Please provide email address.")
            return render_template("signup.html")
        elif not request.form.get("password"):
            flash("Please enter a password.")
            return render_template("signup.html")
        
        rows = db.execute(f"SELECT * FROM users WHERE email = ?", (request.form.get("email"), )).fetchall()
        if len(rows) > 0:
            flash("You're already registered!")
            return render_template("signup.html")

        # Create new entry in table
        db.execute("INSERT INTO users (fname, lname, email, password, cash) VALUES (?,?,?,?,?)", (request.form.get("fname"), request.form.get("lname"), request.form.get("email"), request.form.get("password"), 10000))
        id = (db.execute("SELECT id FROM users WHERE email = ?", (request.form.get("email"), )).fetchall())[0][0]
        db.execute("CREATE TABLE IF NOT EXISTS user"+str(id)+" (stock varchar(15), company varchar(127), num_shares int)")
        db.commit()
        return redirect("/login")

    if request.method == "GET":
        return render_template("signup.html")

@app.route("/home", methods=['GET'])
def home():
    stock_data = db.execute("SELECT * FROM user"+str(session['user_id'])).fetchall()
    total_amt = 0
    total_shares = 0

    # Generate a stock list for the user in question
    for i in range(len(stock_data)):
        stock_data[i] = list(stock_data[i])
        stock_data[i][0] = stock_data[i][0].upper()
        company, val = lookup(stock_data[i][0]) # Lookup stock data
        stock_data[i].append(round(val, 2))
        total_amt += stock_data[i][2] * stock_data[i][3]
        total_shares += stock_data[i][2]
    
    # Retrieve the amount of free cash belonging to the user
    cash = round((db.execute("SELECT cash FROM users WHERE id = ?", (session['user_id'], )).fetchall())[0][0], 2)
    stock_data.append(["CASH", "—", "—", cash])
    total_amt += cash

    # Append row to the stock list with totals
    stock_data.append(["TOTAL", "—", total_shares, round(total_amt, 2)])

    # Pass the list into the HTML template for custom rendering
    return render_template("home.html", stock_data=stock_data, num_cols=len(stock_data[0]))


@app.route("/quote", methods=['GET', 'POST'])
def quote():

    # Generate a quote for the requested stock and display it's trends in a graph
    if request.method == "POST":
        stock = request.form.get("stock")
        company, val = lookup(stock)
        
        # Error handling in case stock or company don't exist
        if not stock:
            flash("Don't forget to enter a stock!")
            return render_template("quote.html", quote=None)
        if not company:
            flash("Looks like that stock doesn't exist.")
            return render_template("quote.html", quote=None)
        
        df = get_history(stock) # Get recent trends for the stock
        x, y = df['date'].to_list(), df['close'].to_list() # Convert the stock trends to a usable list format

        # Pass in recent stock trends so they can be displayed graphically
        return render_template("quote.html", company=company, quote=val, y_vals=y)
    
    if request.method == "GET":
        return render_template("quote.html", quote=None)

@app.route("/buy", methods=['GET', 'POST'])
def buy():
    if request.method == "POST":
        stock = request.form.get("stock")
        num_shares = int(0 if request.form.get("num_shares") is None else request.form.get("num_shares"))
        total_shares = num_shares
        company, val = lookup(stock)

        # Error handling in case of missing fields
        if stock == None or num_shares <= 0 or company == None:
            flash("That's an error. Check that you've entered all information correctly.")
            return render_template("buy.html")
            
        # Check that the user has enough cash to purchase the requested stocks
        cash = (db.execute("SELECT cash FROM users WHERE id = ?", (session['user_id'], )).fetchall())[0][0]
        if cash < num_shares*val:
            flash("That's an error. You don't have enough cash.")
            return render_template("buy.html")

        # Update the user's information in the database to reflect newly purchased stocks and reduced cash
        stocks_from_table = db.execute("SELECT * FROM user"+str(session['user_id'])+" WHERE stock = ?", (stock, )).fetchall()
        if len(stocks_from_table) > 1:
            flash("That's an (internal) error.")
        elif len(stocks_from_table) == 1:
            total_shares += stocks_from_table[0][2]
            db.execute("UPDATE user"+str(session['user_id'])+" SET num_shares = ? WHERE stock = ?", (total_shares, stock))
        else:
            db.execute("INSERT INTO user"+str(session['user_id'])+" (stock, company, num_shares) VALUES (?,?,?)", (stock, company, num_shares))
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash - num_shares*val, session['user_id']))
        db.commit()
        print("success")

    return render_template("buy.html")

@app.route("/sell", methods=['GET', 'POST'])
def sell():
    if request.method == "POST":
        stock = request.form.get("stock")
        num_shares = int(0 if request.form.get("num_shares") is None else request.form.get("num_shares"))
        company, val = lookup(stock)

        # Error handling in case of missing fields
        if stock == None or num_shares <= 0 or company == None:
            flash("That's an error. Check that you've entered all information correctly.")
            return render_template("sell.html")
        
        # Handle errors: not enough cash, stock not yet purchased, attempting to sell more shares than were bought
        num_shares_from_table = db.execute("SELECT num_shares FROM user"+str(session['user_id'])+" WHERE stock = ?", (stock, )).fetchall()
        if len(num_shares_from_table) < 1:
            flash("That's an error. You haven't bought that stock yet!")
            return render_template("sell.html")
        elif len(num_shares_from_table) > 1:
            flash("That's an (internal) error.")
        elif num_shares > num_shares_from_table[0][0]:
            flash("That's an error. You haven't bought that many shares!")
            return render_template("sell.html")

        # Update the user's data to reflect stocks that were sold
        elif num_shares == num_shares_from_table[0][0]:
            db.execute("DELETE from user"+str(session['user_id'])+" WHERE stock = ?", (stock,))
        elif num_shares < num_shares_from_table[0][0]:
            db.execute("UPDATE user"+str(session['user_id'])+" SET num_shares = ? WHERE stock = ?", (num_shares_from_table[0][0] - num_shares, stock))

        # Update the amount of cash
        cash = (db.execute("SELECT cash FROM users WHERE id = ?", (session['user_id'], )).fetchall())[0][0]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", (cash + num_shares*val, session['user_id']))
        db.commit()

    return render_template("sell.html")

@app.route("/logout", methods=['GET', 'DELETE'])
def logout():
    session.clear() # Clear session data so a new user can log in
    return redirect("/") # Redirect to the homepage