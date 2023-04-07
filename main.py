# -*- coding: utf-8 -*-
import requests
import bs4
import time
import datetime
import pandas as pd
import seaborn as sns
import os

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
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S.")


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
    for i, btp_url in enumerate(bonds["url"].to_list()):
        print(i, btp_url)
        infos.append(get_btp_info(btp_url))
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
        df["Reference price date"], format="%Y/%m/%d"
    )
    return df


if __name__ == "__main__":
    timestamp = get_timestamp()
    mk_save_path()
    # STEP 1: get list of bonds
    bond_ls_df = get_all_bonds()
    bond_ls_df.to_csv(f"{SAVE_PATH}/{timestamp}-bond-lists.csv", index=False)
    # STEP 2: get data for each bond
    bonds_df = get_bonds_info(bond_ls_df)
    bonds_df.to_csv(f"{SAVE_PATH}/{timestamp}-bonds-raw.csv", index=False)
    #####################################################
    # STEP 3: data analysis
    # bonds_df = pd.read_csv("./data/.csv")
    # df = clean_df(bonds_df)
    # df["Emittente"] = df["Emittente"].str.lower()
    # df = df[df["Valuta di Negoziazione/ Liquidazione"] == "EUR/EUR"]
    # df = df[df["Tipologia"].str.contains("stato").fillna(False)]
    # df = df[df["Struttura Bond"] == "Plain Vanilla"]
    # df = df[
    #     (df["Emittente"] == "ministero dell'economia e delle finanze")
    #     | (df["Emittente"].str.contains("aus"))
    #     | (df["Emittente"].str.contains("bel"))
    #     | (df["Emittente"].str.contains("fra"))
    #     | (df["Emittente"].str.contains("ted"))
    #     | (df["Emittente"].str.contains("ola"))
    # ]

    # df["Scadenza"] = pd.to_datetime(df["Scadenza"], format="%Y-%m-%d", errors="coerce")
    # df = df[df["Scadenza"] > datetime.datetime.now()]
    # df = df.sort_values("Scadenza")

    # df2 = df
    # df2["maxTRESnetto"] = df2.groupby("Emittente")[
    #     "Rendimento effettivo a scadenza netto"
    # ].transform(lambda x: x.cummax())
    # df2 = df2[df2["maxTRESnetto"] == df2["Rendimento effettivo a scadenza netto"]]

    # sns.lineplot(
    #     data=df2, x="Scadenza", y="maxTRESnetto", hue="Emittente",
    # )
    # ax = sns.scatterplot(
    #     data=df,
    #     x="Scadenza",
    #     y="Rendimento effettivo a scadenza netto",
    #     hue="Emittente",
    #     hue_order=df2["Emittente"].unique(),
    #     s=100,
    # )
    # df2.apply(
    #     lambda x: ax.text(x["Scadenza"], x["maxTRESnetto"], x["Codice Isin"]), axis=1
    # )
