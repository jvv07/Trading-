"""
Stock universes for the scanner.
"""

SP100 = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","BRK-B","UNH","LLY",
    "JPM","XOM","JNJ","V","MA","HD","PG","COST","AVGO","MRK",
    "CVX","ABBV","KO","PEP","ORCL","BAC","MCD","ABT","WMT","CRM",
    "ACN","TMO","LIN","AMD","ADBE","TXN","PM","DHR","NEE","QCOM",
    "RTX","GE","AMGN","HON","SPGI","NFLX","LOW","INTU","IBM","CAT",
    "GS","BKNG","AMAT","SBUX","ISRG","MDT","MS","UPS","VZ","T",
    "BLK","DE","SCHW","AXP","TJX","MU","C","GILD","CB","SO",
    "MMC","SYK","ETN","ADI","ZTS","REGN","CI","PLD","DUK","BDX",
    "ADP","CME","EOG","NOC","ITW","NSC","EMR","WM","AON","CSX",
    "MCO","ICE","EQIX","AMT","PXD","SLB","COP","OKE","ELV","HUM",
]

NASDAQ100 = [
    "AAPL","MSFT","NVDA","AMZN","META","TSLA","GOOGL","AVGO","COST","NFLX",
    "AMD","QCOM","ADBE","INTU","AMAT","MU","LRCX","KLAC","SNPS","CDNS",
    "MRVL","MCHP","ORCL","PANW","CRWD","FTNT","ABNB","DXCM","IDXX","ISRG",
    "MRNA","REGN","VRTX","BIIB","ILMN","ALGN","NXPI","FAST","ODFL","CTAS",
    "PAYX","VRSK","ANSS","CPRT","GEHC","KDP","PCAR","HON","ASML","ON",
]

SECTORS = {
    "Technology": [
        "AAPL","MSFT","NVDA","AMD","INTC","AVGO","QCOM","TXN","AMAT","LRCX",
        "KLAC","ADBE","CRM","ORCL","IBM","NOW","SNPS","CDNS","PANW","CRWD",
    ],
    "Financials": [
        "JPM","BAC","WFC","GS","MS","C","AXP","V","MA","BLK",
        "SPGI","MCO","CME","ICE","SCHW","CB","MMC","AON","TRV","PGR",
    ],
    "Healthcare": [
        "UNH","LLY","JNJ","ABBV","MRK","ABT","TMO","DHR","AMGN","GILD",
        "REGN","VRTX","ISRG","MDT","CVS","ELV","HUM","BIIB","DXCM","IDXX",
    ],
    "Energy": [
        "XOM","CVX","COP","EOG","SLB","MPC","PSX","VLO","OKE","KMI",
        "HAL","BKR","DVN","PXD","FANG","WMB","HES","MRO","APA","NOV",
    ],
    "Consumer Disc.": [
        "AMZN","TSLA","HD","MCD","NKE","SBUX","TGT","LOW","TJX","BKNG",
        "MAR","HLT","RCL","F","GM","ORLY","AZO","ROST","EBAY","ETSY",
    ],
    "Industrials": [
        "GE","HON","CAT","RTX","DE","LMT","NOC","GD","EMR","ETN",
        "ITW","PH","CMI","ROK","URI","CSX","NSC","UPS","FDX","WM",
    ],
    "Communication": [
        "META","GOOGL","NFLX","T","VZ","DIS","CMCSA","CHTR","EA","TTWO",
        "ATVI","SNAP","PINS","MTCH","WBD","PARA","FOX","NWSA","NYT","IAC",
    ],
}

SECTOR_ETFS = {
    "Technology":       "XLK",
    "Financials":       "XLF",
    "Healthcare":       "XLV",
    "Energy":           "XLE",
    "Consumer Disc.":   "XLY",
    "Consumer Staples": "XLP",
    "Industrials":      "XLI",
    "Materials":        "XLB",
    "Real Estate":      "XLRE",
    "Utilities":        "XLU",
    "Comm. Services":   "XLC",
}

# Approximate S&P 500 sector weights (%) for treemap sizing
SECTOR_WEIGHTS = {
    "Technology":       30.2,
    "Financials":       13.0,
    "Healthcare":       12.5,
    "Consumer Disc.":   10.5,
    "Comm. Services":    8.8,
    "Industrials":       8.3,
    "Consumer Staples":  5.9,
    "Energy":            3.9,
    "Utilities":         2.5,
    "Real Estate":       2.3,
    "Materials":         2.1,
}

UNIVERSE_OPTIONS = {
    "S&P 100":          SP100,
    "NASDAQ 100":       NASDAQ100,
    "Technology":       SECTORS["Technology"],
    "Financials":       SECTORS["Financials"],
    "Healthcare":       SECTORS["Healthcare"],
    "Energy":           SECTORS["Energy"],
    "Consumer Disc.":   SECTORS["Consumer Disc."],
    "Industrials":      SECTORS["Industrials"],
    "Communication":    SECTORS["Communication"],
}
