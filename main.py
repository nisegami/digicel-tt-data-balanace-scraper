import json
import math
import sqlite3
import datetime
import os, os.path

import toml
import typer
import pyvirtualdisplay
import selenium.common, selenium.webdriver

app = typer.Typer()


@app.command()
def init(config_file):
    if not os.path.isfile(config_file):
        typer.echo("Could not find that config file!")
        raise typer.Exit(code=1)

    config = toml.load(config_file)
    with sqlite3.connect(config["paths"]["database"]) as con:
        cur = con.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS data_balance_history (id integer primary key AUTOINCREMENT, data_balance numeric NOT NULL, timestamp date DEFAULT (datetime('now','localtime')))")
        cur.close()


@app.command()
def scrape(config_file):
    if not os.path.isfile(config_file):
        typer.echo("Could not find that config file!")
        raise typer.Exit(code=1)
    config = toml.load(config_file)

    selenium_options = selenium.webdriver.FirefoxOptions()
    selenium_options.add_argument("--headless")

    display_settings = {"backend": config["display"]["backend"], "size": (config["display"]["width"], config["display"]["height"])}

    if display_settings["backend"] == "xvnc":
        if "rfbport" in config["display"]:
            display_settings["rfbport"] = config["display"]["rfbport"]
        else:
            typer.echo("Please provide an RFB Port when using XVNC!")
            raise typer.Exit(code=1)

    with typer.progressbar(length=100) as progress:
        with pyvirtualdisplay.Display(**display_settings) as _:
            progress.update(20)
            with selenium.webdriver.Firefox(options=selenium_options) as driver:
                driver.implicitly_wait(15)
                progress.update(20)

                driver.get("https://mydigicel.digicelgroup.com/home")
                progress.update(5)

                email_tab_button = driver.find_element_by_link_text("Email")
                email_tab_button.click()
                progress.update(5)

                email_field = driver.find_element_by_name("email")
                email_field.send_keys(config["auth"]["email"])

                password_field = driver.find_element_by_name("password")
                password_field.send_keys(config["auth"]["password"])

                login_button = driver.find_element_by_id("loginSubmitButton")
                login_button.click()
                progress.update(50)

                try:
                    data_remaining_span = driver.find_element_by_xpath('//span[contains(text(), "GB")]')
                    data_remaining = float(data_remaining_span.text.split()[0])
                except ValueError:
                    # Not a number
                    typer.echo(f"Did not receive a number from Digicel's site: {data_remaining_span.text.split()[0]}")
                    raise typer.Exit(code=1)
                except selenium.common.exceptions.NoSuchElementException:
                    # Digicel site failure
                    typer.echo("Digicel's site failed to load.")
                    raise typer.Exit(code=1)
                except Exception as e:
                    typer.echo(f"An unknown error occured: {e}")
                    raise typer.Exit(code=1)

        with sqlite3.connect(config["paths"]["database"]) as con:
            cur = con.cursor()
            cur.execute("INSERT INTO data_balance_history (data_balance) VALUES (?)", (data_remaining,))
            cur.close()
            typer.echo("\nSuccessfully wrote result to database.")

        data = {"data_balance": data_remaining, "last_updated": datetime.datetime.now().isoformat()}
        with open(config["paths"]["api"], "w") as outfile:
            outfile.write(json.dumps(data))
            typer.echo("Successfully wrote result to API file.")

        typer.echo(f"Your remaining balance is {data_remaining} GB as of {datetime.datetime.now().ctime()}.")


if __name__ == "__main__":
    app()
