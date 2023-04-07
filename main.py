# -*- coding: utf-8 -*-
import requests
import bs4
import time
import datetime
import os

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

URL_BASE = "https://www.borsaitaliana.it"
URL_BONDS_TEMPLATE = "/borsa/obbligazioni/mot/{}/lista.html?lang=en&page="
BOND_SECTIONS = [
    "btp",
    "obbligazioni-euro",
    "euro-obbligazioni",
    "cct",
    "../green-e-social-bond",
]
SAVE_PATH = "./data"
BACKOFF_TIME = 0.5


def get_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def mk_save_path():
    if not os.path.exists(SAVE_PATH):
        os.mkdir(SAVE_PATH)


def get_bonds_at_page(url, i):
    r = requests.get(f"{URL_BASE}{url}{i}")
    soup = bs4.BeautifulSoup(r.content.decode("utf-8"), features="lxml")
    bonds = soup.find_all("tr")[2:]
    return [btp.find("a")["href"] for btp in bonds]


def get_bonds(url):
    bonds = []
    for i in range(1, 1000):
        print(f"At page: {i}")
        page_bonds = get_bonds_at_page(url, i)
        bonds += page_bonds
        if len(page_bonds) == 0:
            break
        time.sleep(BACKOFF_TIME)
    return bonds


def get_all_bonds():
    bonds = []
    for section in BOND_SECTIONS:
        print("At section:", section)
        bonds += get_bonds(URL_BONDS_TEMPLATE.format(section))
    df = pd.DataFrame(bonds, columns=["url"])
    return df


def get_btp_info(btp_url):
    r = requests.get(f"{URL_BASE}{btp_url}")
    soup = bs4.BeautifulSoup(r.content.decode("utf-8"), features="lxml")
    rows = soup.find_all("tr")
    rows = [row.find_all("td") for row in rows]
    rows = [[cell.text.strip() for cell in row] for row in rows]
    return {row[0]: row[1] for row in rows if len(row) == 2}


def get_bonds_info(bonds):
    infos = []
    urls = bonds["url"].to_list()
    for i, btp_url in enumerate(urls):
        print(f"{i:04}/{len(urls):04}", btp_url)
        try:
            infos.append(get_btp_info(btp_url))
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(BACKOFF_TIME)
    return pd.DataFrame(infos)


def to_float(x):
    if isinstance(x, float):
        return x
    x = x.replace(",", "")
    try:
        return float(x) if x else float("NaN")
    except Exception as e:
        print(f"Error '{e}' when parsing float '{x}', default to NaN")
        return float("NaN")


def clean_df(df):
    # drop columns that are not interesting
    df = df.drop(columns=["Put", "Call"])

    # parse floating points (in)
    for c in [
        "Official Close",
        "Opening",
        "Last Volume",
        "Total Quantity",
        "Number Trades",
        "Day Low",
        "Day High",
        "Year Low",
        "Year High",
        "Gross yield to maturity",
        "Net yield to maturity",
        "Gross accrued interest",
        "Net accrued interest",
        "Modified Duration",
        "Reference price",
        "Outstanding",
        "Lot Size",
        "Next Coupon",
    ]:
        df[c] = df[c].apply(to_float)
    for c in [
        "Official Close Date",
        "First Day of Trading",
        "Interest Commencement Date",
        "First Coupon Date",
        "Last Payment Date",
        "Expiry Date",
    ]:
        df[c] = pd.to_datetime(df[c], format="%y/%m/%d")

    df["Reference price date"] = pd.to_datetime(
        df["Reference price date"], format="%d/%m/%Y"
    )
    return df


def posix_timestamp_to_str(x):
    return datetime.datetime.fromtimestamp(x).strftime("%Y-%m")


if __name__ == "__main__":
    # timestamp = get_timestamp()
    # mk_save_path()
    # STEP 1: get list of bonds
    # bond_ls_df = get_all_bonds()
    # bond_ls_df.to_csv(f"{SAVE_PATH}/{timestamp}-bond-lists.csv", index=False)
    # STEP 2: get data for each bond
    # bonds_df = get_bonds_info(bond_ls_df)
    # bonds_df.to_csv(f"{SAVE_PATH}/{timestamp}-bonds-raw.csv", index=False)
    #####################################################
    # STEP 3: data analysis
    bonds_df = pd.read_csv("./data/2023-04-07_10-15-04-bonds-raw.csv")
    df = clean_df(bonds_df)

    # Do not want exchange rate risk
    df = df[df["Negotiation Currency/ Settlement currency"] == "EUR/EUR"]

    # Just interested in Public Debt Bonds
    df = df[df["Tipology"].isin(["Italian Government Bonds", "Foreign Public Debt"])]

    # Consider just Plain Vanilla to remove other external variables
    df = df[df["Bond Structure"] == "Plain Vanilla"]

    # Get the county and filter
    df["Country"] = df["Isin Code"].apply(lambda x: x[:2])
    df = df[df["Country"].isin(["IT", "AT", "BE", "DE", "FI", "FR", "NL"])]

    # Plot the envelope of the maximum Net yield to maturity
    df = df.sort_values("Expiry Date")
    df = df[df["Expiry Date"] > datetime.datetime.now()]
    df["ExpiryTimestamp"] = df["Expiry Date"].apply(lambda x: x.timestamp())
    df["maxNTM"] = df.groupby("Country")["Net yield to maturity"].apply(
        lambda x: x.cummax()
    )
    df2 = df[df["maxNTM"] == df["Net yield to maturity"]]

    sns.lmplot(
        data=df,
        x="ExpiryTimestamp",
        y="Net yield to maturity",
        hue="Country",
        hue_order=df2["Country"].unique(),
        lowess=True,
        line_kws={"alpha": 0.3, "linewidth": 5},
    )
    ax = plt.gca()
    sns.lineplot(
        data=df2, x="ExpiryTimestamp", y="maxNTM", hue="Country", ax=ax, legend=False
    )
    df2.apply(
        lambda x: ax.text(x["ExpiryTimestamp"], x["maxNTM"], x["Isin Code"]), axis=1
    )
    xticks = np.linspace(df["ExpiryTimestamp"].min(), df["ExpiryTimestamp"].max(), 10)
    ax.set_xticks(xticks)

    ax.set_xticklabels([posix_timestamp_to_str(x) for x in xticks])
