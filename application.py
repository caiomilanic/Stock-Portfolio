import os
import datetime
import re

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Create a portfolio table in database
db.execute("CREATE TABLE IF NOT EXISTS 'portfolio' ('username' TEXT NOT NULL, 'operation' VARCHAR(4) NOT NULL, 'symbol' VARCHAR(4) NOT NULL, 'shares' INTEGER NOT NULL, 'price' NUMERIC NOT NULL, 'date' INTEGER NOT NULL)")

# Define datetime variable
currentDT = datetime.datetime.now()

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Function to check if special character
def run(string):

    regex = re.compile('[,.@_!#$%^&*()<>?/\|}{~:]')

    # Pass the string in search
    # method of regex object
    if(regex.search(string) == None):
        return apology("Do not inform any special characters")


# Function to get unique values
def unique(list1):

    # Intilize a null list
    unique_list = []

    # Traverse for all elements
    for x in list1:

        # Check if exists in unique_list or not
        if x not in unique_list:
            unique_list.append(x)
    return unique_list


@app.route("/")
@login_required
def index():

    # Select information from user
    user_info = db.execute("SELECT * FROM users WHERE username = :username",
                            username = session["username"])
    # Select all user's operations
    rows = db.execute("SELECT * FROM portfolio WHERE username = :username",
                      username = session["username"])

    stock_list = []

    # Append all symbols from portfolio on a list
    for row in rows:
        stock_list.append(row["symbol"])

    # Call 'unique' function to get a list with only different symbols
    symbols = unique(stock_list)

    # Check how many shares user has

    shares_list = []

    i = 0

    while i < len(symbols):
        counter = 0
        for row in rows:
            # If operantion "BUY" increment counter
            if symbols[i] == row["symbol"] and row["operation"] == "BUY":
                counter = (counter + row["shares"])
            # If operation "Sell" decrement counter
            elif symbols[i] == row["symbol"] and row["operation"] == "SELL":
                counter = (counter - row["shares"])
        # Append each symbol's counter on shares_list
        shares_list.append(counter)
        i += 1


    # Define the variables to be displayed
    symbols_size = len(symbols)
    quoted = []
    total = []
    cash = round(user_info[0]["cash"], 2)
    final_total = 0

    # Call quote function to every symbol in symbols list
    j = 0
    while j < len(symbols):
        quoted.append(lookup(symbols[j]))

        j += 1

    # Calculate totals and append to list
    l = 0
    while l < len(symbols):
        total.append(round(shares_list[l] * quoted[l]["price"], 2))

        l += 1

    # Calculate the sum of all totals in total list
    for i in total:
        final_total = round(final_total + i, 2)

    return render_template("index.html", symbols = symbols, shares_list = shares_list, quoted = quoted, symbols_size = symbols_size,
                            total = total, cash = cash, final_total = final_total)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]


        session["username"] = rows[0]["username"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    # Method GET will return the template
    if request.method == "GET":
        return render_template("buy.html")

    # Method POST will work with user's inputs
    else:

        # Define variables using user's inputs
        buy_symbol = request.form.get("symbol")
        quoted_symbol = lookup(buy_symbol)
        shares = request.form.get("shares")

        # Prompt error in case of blank form
        if not buy_symbol:
            return apology("must inform symbol")

        # Prompt error if symbol doesn't match with API
        elif not quoted_symbol:
            return apology("invalid symbol")

        # Prompt error if invalid number of shares
        elif not shares or int(shares) <= 0:
            return apology("invalid number of shares")

        # Only then procede with buying operation
        else:
            # Query the information about the loged user
            rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username = session["username"])

            # Calculate operation value and define variable
            buy_cost = float(quoted_symbol["price"]) * int(shares)

            # Check if user has the amount of cash for the operation
            if buy_cost > rows[0]["cash"]:
                return apology("not enough cash")

            else:
                # Register of the buy operation
                db.execute("INSERT INTO portfolio (username, operation, symbol, shares, price, date) VALUES (:username, :operation, :symbol, :shares, :price, :date)",
                username = session["username"], operation = "BUY", symbol = buy_symbol, shares = shares, price = quoted_symbol["price"],
                date = currentDT.strftime("%Y-%m-%d %H:%M:%S"))

                # Calculate user's balance
                buy_balance = rows[0]["cash"] - buy_cost

                # Update user's cash
                db.execute("UPDATE users SET cash = :cash WHERE username = :username",
                cash = buy_balance, username = session["username"])
                flash("Shares bought!")
                return redirect("/")

@app.route("/history")
@login_required
def history():

    history = db.execute("SELECT * FROM portfolio WHERE username = :username",
                        username = session["username"])
    counter = 0
    for row in history:
        counter = counter + 1


    return render_template("history.html", history = history, counter = counter)


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():

    # Return html
    if request.method == "GET":
        return render_template("quote.html")
    else:
        # Get stock symbol info
        quote_symbol = request.form.get("symbol")

        # Call quote function
        quote = lookup(request.form.get("symbol"))
        if not quote_symbol:
            return apology("must inform symbol")
        elif not quote:
            return apology("invalid stock symbol")
        else:
            # Return second template calling defined variable
            return render_template("quoted.html", quote=quote)


@app.route("/register", methods=["GET", "POST"])
def register():

    # Return html
    if request.method == "GET":
        return render_template("register.html")
    else:

        # Get username info
        username = request.form.get("username")
        if not username:
            return apology("must provide username")

        # Get and hash password info
        password = generate_password_hash(request.form.get("password"))
        if not password:
            return apology("must provide password")

        # Check if username already used
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                  username = username)

        # If user not yet registered, insert into database
        if not rows:
            db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                username = username, hash = password)
            flash("Registered!")
            return redirect("/")
        else:
            return apology("username already taken")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

     # Method GET will return the template
    if request.method == "GET":
        return render_template("sell.html")

    # Method POST will work with user's inputs
    else:

        # Define variables using user's inputs
        sell_symbol = request.form.get("symbol")
        quoted_symbol = lookup(sell_symbol)
        shares = request.form.get("shares")

        # Prompt error in case of blank form
        if not sell_symbol:
            return apology("must inform symbol")

        # Prompt error if symbol doesn't match with API
        elif not quoted_symbol:
            return apology("invalid symbol")

        # Prompt error if invalid number of shares
        elif not shares or int(shares) <= 0:
            return apology("invalid number of shares")

        # Only then procede with selling operation
        else:
            # Query the information about the loged user
            rows = db.execute("SELECT * FROM portfolio WHERE username = :username",
                          username = session["username"])

            # Calculate operation value and define variable
            sell_gain = float(quoted_symbol["price"]) * int(shares)

            # Check number of shares user's possess

            counter = 0
            for row in rows:
                if sell_symbol == row["symbol"] and row["operation"] == "BUY":
                    counter = (counter + row["shares"])
                elif sell_symbol == row["symbol"] and row["operation"] == "SELL":
                    counter = (counter - row["shares"])

            # Allow operation if user possess equal or more shares
            if int(counter) < int(shares):
                return apology("user don't have this much shares")

            else:

                # Register sell operation
                db.execute("INSERT INTO portfolio (username, operation, symbol, shares, price, date) VALUES (:username, :operation, :symbol, :shares, :price, :date)",
                username = session["username"], operation = "SELL", symbol = sell_symbol, shares = shares, price = quoted_symbol["price"],
                date = currentDT.strftime("%Y-%m-%d %H:%M:%S"))

                # Calculate user's balance
                user_info = db.execute("SELECT * FROM users WHERE username = :username",
                                        username = session["username"])

                sell_balance = user_info[0]["cash"] + sell_gain

                # Update user's cash
                db.execute("UPDATE users SET cash = :cash WHERE username = :username",
                cash = sell_balance, username = session["username"])

            flash("Shares sold!")
            return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
