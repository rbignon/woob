BANK_TRANSACTION_CODES = {
    # Defines every combination for bank transaction codes.
    # This allows to check if the code returned by the bank
    # is valid according to the ISO20022 standard.
    "ACMT": {
        "ACOP": (
            "PSTE",
            "BCKV",
            "ERTA",
            "FLTA",
            "VALD",
            "YTDA",
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "ADOP": (
            "BCKV",
            "ERTA",
            "FLTA",
            "PSTE",
            "VALD",
            "YTDA",
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "NTAV": ("NTAV",),
        "OPCL": (
            "ACCC",
            "ACCO",
            "ACCT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "OTHR": ("OTHR", "NTAV"),
    },
    "CAMT": {
        "ACCB": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "DSBR",
            "CAJT",
            "XBRD",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "ODFT",
            "RIMB",
            "SWEP",
            "TAXE",
            "TOPG",
            "ZABA",
        ),
        "CAPL": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "XBRD",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "NTAV": ("NTAV",),
        "OTHR": ("OTHR", "NTAV"),
    },
    "CMDT": {
        "DLVR": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "FTUR": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "NTAV": ("NTAV",),
        "OPTN": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "OTHR": ("OTHR", "NTAV"),
        "SPOT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
    },
    "DERV": {
        "LFUT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "LOPT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "NTAV": ("NTAV",),
        "OBND": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "OCRD": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "OEQT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "OIRT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "OSED": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "OSWP": (
            "CHRG",
            "SWCC",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "SWFP",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "SWPP",
            "RIMB",
            "SWRS",
            "TAXE",
            "SWUF",
        ),
        "OTHR": ("OTHR", "NTAV"),
    },
    "XTND": {"NTAV": ("NTAV",)},
    "FORX": {
        "FWRD": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "FTUR": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "NDFX": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "NTAV": ("NTAV",),
        "OTHR": ("OTHR", "NTAV"),
        "SPOT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "SWAP": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
    },
    "LDAS": {
        "CSLN": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "DDWN",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "PPAY",
            "RIMB",
            "RNEW",
            "TAXE",
        ),
        "FTDP": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "DPST",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "RPMT",
            "TAXE",
        ),
        "FTLN": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "DDWN",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "PPAY",
            "RIMB",
            "RNEW",
            "TAXE",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MGLN": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "DDWN",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "PPAY",
            "RIMB",
            "RNEW",
            "TAXE",
        ),
        "NTAV": ("NTAV",),
        "NTDP": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "DPST",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "RPMT",
            "TAXE",
        ),
        "NTLN": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "DDWN",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "PPAY",
            "RIMB",
            "RNEW",
            "TAXE",
        ),
        "OTHR": ("OTHR", "NTAV"),
        "SYDN": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "DDWN",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "PPAY",
            "RIMB",
            "RNEW",
            "TAXE",
        ),
    },
    "PMNT": {
        "CNTR": (
            "BCDP",
            "BCWD",
            "CDPT",
            "CWDL",
            "CHRG",
            "CHKD",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "FCDP",
            "FCWD",
            "INTR",
            "MSCD",
            "MIXD",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
            "TCDP",
            "TCWD",
        ),
        "CCRD": (
            "CDPT",
            "CWDL",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "POSC",
            "XBCW",
            "XBCP",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "POSD",
            "RIMB",
            "SMRT",
            "TAXE",
        ),
        "DRFT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "DDFT",
            "UDFT",
            "DMCG",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "STAM",
            "STLR",
            "TAXE",
        ),
        "ICCN": (
            "ACON",
            "BACT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "COAT",
            "CAJT",
            "XICT",
            "DAJT",
            "FEES",
            "FIOA",
            "INTR",
            "ICCT",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "ICHQ": (
            "ARPD",
            "BCHQ",
            "CASH",
            "CSHA",
            "CCCH",
            "CHRG",
            "CCHQ",
            "CQRV",
            "URCQ",
            "CLCQ",
            "COMM",
            "COME",
            "COMI",
            "CDIS",
            "CAJT",
            "CRCQ",
            "DAJT",
            "FEES",
            "XBCQ",
            "XRCQ",
            "INTR",
            "NPCC",
            "COMT",
            "NTAV",
            "OPCQ",
            "ORCQ",
            "OTHR",
            "RIMB",
            "TAXE",
            "UPCQ",
            "XPCQ",
        ),
        "ICDT": (
            "ACOR",
            "ACDT",
            "ADBT",
            "APAC",
            "ARET",
            "AREV",
            "ASET",
            "ATXN",
            "AUTT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "VCOM",
            "XBCT",
            "XBSA",
            "XBST",
            "DAJT",
            "DMCT",
            "FEES",
            "FICT",
            "INTR",
            "BOOK",
            "COMT",
            "ENCT",
            "NTAV",
            "OTHR",
            "SALA",
            "PRCT",
            "RIMB",
            "RPCR",
            "RRTN",
            "XRTN",
            "SDVA",
            "ESCT",
            "STDO",
            "TAXE",
            "TTLS",
        ),
        "IDDT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "XBDD",
            "DAJT",
            "PMDD",
            "URDD",
            "FEES",
            "FIDD",
            "INTR",
            "COMT",
            "NTAV",
            "OODD",
            "OTHR",
            "PADD",
            "RIMB",
            "RCDD",
            "PRDD",
            "UPDD",
            "BBDD",
            "ESDD",
            "TAXE",
        ),
        "IRCT": (
            "ACOR",
            "ACDT",
            "ADBT",
            "APAC",
            "ARET",
            "AREV",
            "ASET",
            "ATXN",
            "AUTT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "VCOM",
            "XBCT",
            "XBSA",
            "XBST",
            "DAJT",
            "DMCT",
            "FEES",
            "FICT",
            "INTR",
            "BOOK",
            "COMT",
            "ENCT",
            "NTAV",
            "OTHR",
            "SALA",
            "PRCT",
            "RIMB",
            "RPCR",
            "RRTN",
            "XRTN",
            "SDVA",
            "ESCT",
            "STDO",
            "TAXE",
            "TTLS",
        ),
        "LBOX": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "LBCA",
            "CAJT",
            "LBDB",
            "DAJT",
            "LBDP",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MCRD": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "POSC",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "POSP",
            "RIMB",
            "SMCD",
            "TAXE",
            "UPCT",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
            "IADD",
        ),
        "NTAV": ("NTAV",),
        "OTHR": ("OTHR", "NTAV"),
        "RCCN": (
            "ACON",
            "BACT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "COAT",
            "CAJT",
            "XICT",
            "DAJT",
            "FEES",
            "FIOA",
            "INTR",
            "ICCT",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "RCHQ": (
            "ARPD",
            "BCHQ",
            "CASH",
            "CSHA",
            "CCCH",
            "CHRG",
            "CCHQ",
            "CQRV",
            "URCQ",
            "CLCQ",
            "COMM",
            "COME",
            "COMI",
            "CDIS",
            "CAJT",
            "CRCQ",
            "DAJT",
            "FEES",
            "XBCQ",
            "XRCQ",
            "INTR",
            "NPCC",
            "COMT",
            "NTAV",
            "OPCQ",
            "ORCQ",
            "OTHR",
            "RIMB",
            "TAXE",
            "UPCQ",
            "XPCQ",
        ),
        "RCDT": (
            "ACOR",
            "ACDT",
            "ADBT",
            "APAC",
            "ARET",
            "AREV",
            "ASET",
            "ATXN",
            "AUTT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "VCOM",
            "XBCT",
            "XBSA",
            "XBST",
            "DAJT",
            "DMCT",
            "FEES",
            "FICT",
            "INTR",
            "BOOK",
            "COMT",
            "ENCT",
            "NTAV",
            "OTHR",
            "SALA",
            "PRCT",
            "RIMB",
            "RPCR",
            "RRTN",
            "XRTN",
            "SDVA",
            "ESCT",
            "STDO",
            "TAXE",
            "TTLS",
        ),
        "RDDT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "XBDD",
            "DAJT",
            "PMDD",
            "URDD",
            "FEES",
            "FIDD",
            "INTR",
            "COMT",
            "NTAV",
            "OODD",
            "OTHR",
            "PADD",
            "RIMB",
            "RCDD",
            "PRDD",
            "UPDD",
            "BBDD",
            "ESDD",
            "TAXE",
        ),
        "RRCT": (
            "ACOR",
            "ACDT",
            "ADBT",
            "APAC",
            "ARET",
            "AREV",
            "ASET",
            "ATXN",
            "AUTT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "VCOM",
            "XBCT",
            "XBSA",
            "XBST",
            "DAJT",
            "DMCT",
            "FEES",
            "FICT",
            "INTR",
            "BOOK",
            "COMT",
            "ENCT",
            "NTAV",
            "OTHR",
            "SALA",
            "PRCT",
            "RIMB",
            "RPCR",
            "RRTN",
            "XRTN",
            "SDVA",
            "ESCT",
            "STDO",
            "TAXE",
            "TTLS",
        ),
    },
    "PMET": {
        "DLVR": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "FTUR": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "NTAV": ("NTAV",),
        "OPTN": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "OTHR": ("OTHR", "NTAV"),
        "SPOT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
    },
    "SECU": {
        "BLOC": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "XCHG",
            "XCHC",
            "XCHN",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTCG",
            "OTCC",
            "OTCN",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "COLL": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CMBO",
            "CMCO",
            "CPRB",
            "CAJT",
            "DAJT",
            "EQBO",
            "EQCO",
            "FEES",
            "FWBC",
            "FWCC",
            "INTR",
            "SLBC",
            "SLCC",
            "MGCC",
            "MARG",
            "COMT",
            "NTAV",
            "OPBC",
            "OPCC",
            "OTHR",
            "RIMB",
            "REPU",
            "SECB",
            "SECL",
            "SWBC",
            "TAXE",
            "TRPO",
        ),
        "CORP": (
            "BONU",
            "EXRI",
            "CAPG",
            "DVCA",
            "CSLI",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CONV",
            "CAJT",
            "DAJT",
            "DECR",
            "DVOP",
            "DRIP",
            "DRAW",
            "DTCH",
            "SHPR",
            "EXOF",
            "FEES",
            "REDM",
            "MCAL",
            "INTR",
            "PRII",
            "INTR",
            "LIQU",
            "MRGR",
            "COMT",
            "NTAV",
            "ODLT",
            "OTHR",
            "PCAL",
            "PRED",
            "PRIO",
            "BPUT",
            "RWPL",
            "RIMB",
            "BIDS",
            "RHTS",
            "SSPL",
            "TREC",
            "TAXE",
            "TEND ",
            "EXWA",
        ),
        "OTHB": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "XCHG",
            "XCHC",
            "XCHN",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTCG",
            "OTCC",
            "OTCN",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "CUST": (
            "BONU",
            "EXRI",
            "CAPG",
            "DVCA",
            "CSLI",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CONV",
            "CAJT",
            "DAJT",
            "DECR",
            "DVOP",
            "DRIP",
            "DRAW",
            "DTCH",
            "SHPR",
            "EXOF",
            "FEES",
            "REDM",
            "MCAL",
            "INTR",
            "PRII",
            "INTR",
            "LIQU",
            "MRGR",
            "COMT",
            "NTAV",
            "ODLT",
            "OTHR",
            "PCAL",
            "PRED",
            "PRIO",
            "BPUT",
            "RWPL",
            "RIMB",
            "BIDS",
            "RHTS",
            "SSPL",
            "TREC",
            "TAXE",
            "TEND ",
            "EXWA",
        ),
        "COLC": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "LACK": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "CASH": (
            "BKFE",
            "ERWI",
            "BROK",
            "CPEN",
            "CHAR",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CLAI",
            "CAJT",
            "DAJT",
            "GEN2",
            "FEES",
            "INFD",
            "FUTU",
            "FUCO",
            "RESI",
            "PRIN",
            "INTR",
            "ERWA",
            "MNFE",
            "COMT",
            "NTAV",
            "OTHR",
            "OVCH",
            "RIMB",
            "STAM",
            "SWAP",
            "SWEP",
            "TREC",
            "TAXE",
            "TRFE",
            "UNCO",
            "GEN1",
            "WITH",
        ),
        "NSET": (
            "BSBO",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "CROS",
            "DAJT",
            "ISSU",
            "XCHG",
            "XCHC",
            "XCHN",
            "OWNE",
            "FCTA",
            "FEES",
            "INSP",
            "INTR",
            "OWNI",
            "NETT",
            "NSYN",
            "COMT",
            "NTAV",
            "OTCG",
            "OTCC",
            "OTCN",
            "OTHR",
            "PAIR",
            "PLAC",
            "PORT",
            "PRUD",
            "REDM",
            "REAA",
            "RIMB",
            "REPU",
            "RVPO",
            "SECB",
            "SECL",
            "BSBC",
            "SUBS",
            "SUAA",
            "SWIC",
            "SYND",
            "TAXE",
            "TBAC",
            "TRAD",
            "TRIN",
            "TOUT",
            "TRPO",
            "TRVO",
            "TURN",
        ),
        "NTAV": ("NTAV",),
        "OTHR": ("OTHR", "NTAV"),
        "SETT": (
            "BSBO",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "CROS",
            "DAJT",
            "ISSU",
            "XCHG",
            "XCHC",
            "XCHN",
            "OWNE",
            "FCTA",
            "FEES",
            "INSP",
            "INTR",
            "OWNI",
            "NETT",
            "NSYN",
            "COMT",
            "NTAV",
            "OTCG",
            "OTCC",
            "OTCN",
            "OTHR",
            "PAIR",
            "PLAC",
            "PORT",
            "PRUD",
            "REDM",
            "REAA",
            "RIMB",
            "REPU",
            "RVPO",
            "SECB",
            "SECL",
            "BSBC",
            "SUBS",
            "SUAA",
            "SWIC",
            "SYND",
            "TAXE",
            "TBAC",
            "TRAD",
            "TRIN",
            "TOUT",
            "TRPO",
            "TRVO",
            "TURN",
        ),
    },
    "TRAD": {
        "CLNC": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "STAC",
            "STLR",
            "TAXE",
        ),
        "DOCC": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "STAC",
            "STLR",
            "TAXE",
        ),
        "DCCT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "FRZF",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "SABG",
            "SOSE",
            "SOSI",
            "STLR",
            "TAXE",
        ),
        "GUAR": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "STLM",
            "TAXE",
        ),
        "MCOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "MDOP": (
            "ADJT",
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "FEES",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "TAXE",
        ),
        "NTAV": ("NTAV",),
        "OTHR": ("OTHR", "NTAV"),
        "LOCT": (
            "CHRG",
            "COMM",
            "COME",
            "COMI",
            "CAJT",
            "DAJT",
            "FEES",
            "FRZF",
            "INTR",
            "COMT",
            "NTAV",
            "OTHR",
            "RIMB",
            "SABG",
            "SOSE",
            "SOSI",
            "STLR",
            "TAXE",
        ),
    },
}

# Some stet banks don't follow ISO20022 standard but follow a CFONB format
# See: https://www.cfonb.org/fichiers/20190913092943_Brochure_Codes_Operation_pour_restitutions_clienteles_V5_0_novembre_2018.pdf
FRENCH_BANK_TRANSACTION_CODES = {
    "01": ("PMNT", "ICHQ", "CCHQ"),
    "02": ("PMNT", "RCHQ", "CCHQ"),
    "03": ("PMNT", "RCHQ", "UPCQ"),
    "04": ("PMNT", "CCRD", "CDPT"),
    "05": ("PMNT", "RCDT", "DMCT"),
    "06": ("PMNT", "ICDT", "DMCT"),
    "07": ("PMNT", "DRFT", "STAM"),
    "08": ("PMNT", "RDDT", "OTHR"),
    "09": ("PMNT", "IDDT", "OTHR"),
    "10": ("PMNT", "RDDT", "UPDD"),
    "11": ("PMNT", "CCRD", "RIMB"),
    "12": ("PMNT", "ICDT", "RRTN"),
    "13": ("PMNT", "RCCN", "ICCT"),
    "14": ("PMNT", "ICCN", "ICCT"),
    "15": ("PMNT", "RCHQ", "CCHQ"),
    # Missing numbers are also missing in their documentation
    "18": ("PMNT", "RCDT", "DMCT"),
    "21": ("PMNT", "ICDT", "DMCT"),
    "22": ("PMNT", "RDDT", "OODD"),
    "24": ("PMNT", "IDDT", "OODD"),
    "26": ("PMNT", "IDDT", "UPDD"),
    "27": ("PMNT", "RDDT", "UPDD"),
    "28": ("PMNT", "CCRD", "POSD"),
    "29": ("PMNT", "CCRD", "CWDL"),
    "30": ("PMNT", "MCRD", "POSC"),
    "31": ("PMNT", "DRFT", "STAM"),
    "32": ("PMNT", "DRFT", "DDFT"),
    "33": ("PMNT", "DRFT", "UDFT"),
    "34": ("PMNT", "DRFT", "OTHR"),
    "35": ("PMNT", "DRFT", "STAM"),
    "36": ("PMNT", "MCRD", "DAJT"),
    "37": ("PMNT", "DRFT", "DDFT"),
    "38": ("PMNT", "MCRD", "UPCT"),
    "39": ("PMNT", "RCDT", "XBCT"),
    "41": ("PMNT", "ICDT", "XBCT"),
    "42": ("FORX", "MDOP", "OTHR"),
    "43": ("PMNT", "MDOP", "OTHR"),
    "44": ("PMNT", "ICDT", "XBCT"),
    "45": ("PMNT", "RCDT", "XBCT"),
    "46": ("FORX", "SPOT", "OTHR"),
    "47": ("FORX", "SPOT", "OTHR"),
    "48": ("FORX", "FWRD", "OTHR"),
    "49": ("FORX", "FWRD", "OTHR"),
    "51": ("SECU", "SETT", "SUBS"),
    "52": ("SECU", "MDOP", "OTHR"),
    "53": ("SECU", "SETT", "SUBS"),
    "54": ("SECU", "SETT", "REDM"),
    "55": ("SECU", "CASH", "OTHR"),
    "56": ("SECU", "SETT", "SUBS"),
    "57": ("SECU", "SETT", "REDM"),
    "58": ("SECU", "SETT", "SUBS"),
    "59": ("SECU", "SETT", "REDM"),
    "61": ("ACMT", "MDOP", "INTR"),
    "62": ("ACMT", "MDOP", "COMM"),
    "63": ("ACMT", "MCOP", "INTR"),
    "64": ("ACMT", "MDOP", "COMI"),
    "65": ("ACMT", "MDOP", "COME"),
    "66": ("ACMT", "MDOP", "COMT"),
    "67": ("ACMT", "MDOP", "TAXE"),
    "68": ("FORX", "MDOP", "OTHR"),
    "69": ("FORX", "MCOP", "OTHR"),
    "70": ("ACMT", "MDOP", "INTR"),
    "71": ("LDAS", "CSLN", "DDWN"),
    "72": ("LDAS", "CSLN", "PPAY"),
    "73": ("SECU", "CORP", "OTHR"),
    "74": ("SECU", "CORP", "OTHR"),
    "75": ("LDAS", "CSLN", "RIMB"),
    "76": ("LDAS", "FTDP", "DPST"),
    "77": ("LDAS", "FTDP", "RPMT"),
    "80": ("SECU", "SETT", "SUBS"),
    "81": ("SECU", "SETT", "REDM"),
    "82": ("SECU", "SETT", "REDM"),
    "83": ("SECU", "SETT", "REDM"),
    "84": ("SECU", "SETT", "SUBS"),
    "85": ("SECU", "SETT", "REDM"),
    "86": ("SECU", "MDOP", "OTHR"),
    "87": ("SECU", "CUST", "DVCA"),
    "88": ("SECU", "CUST", "COMM"),
    "89": ("SECU", "CUST", "TREC"),
    "90": ("PMNT", "ICDT", "IADD"),
    "91": ("ACMT", "MCOP", "OTHR"),
    "92": ("CAMT", "ACCB", "OTHR"),
    "93": ("CAMT", "ACCB", "OTHR"),
    "94": ("CAMT", "CAPL", "OTHR"),
    "95": ("CAMT", "CAPL", "OTHR"),
    "96": ("PMNT", "RDDT", "PADD"),
    "97": ("PMNT", "IDDT", "PADD"),
    "98": ("PMNT", "IDDT", "UPDD"),
    "99": ("ACMT", "MCOP", "ADJT"),
    "A1": ("PMNT", "IDDT", "ESDD"),
    "A2": ("PMNT", "IDDT", "BBDD"),
    "A3": ("PMNT", "RDDT", "UPDD"),
    "A4": ("PMNT", "RDDT", "UPDD"),
    "A5": ("PMNT", "IDDT", "PRDD"),
    "A6": ("PMNT", "IDDT", "PRDD"),
    "B1": ("PMNT", "RDDT", "ESDD"),
    "B2": ("PMNT", "RDDT", "BBDD"),
    "B3": ("PMNT", "IDDT", "UPDD"),
    "B4": ("PMNT", "IDDT", "UPDD"),
    "B5": ("PMNT", "RDDT", "PRDD"),
    "B6": ("PMNT", "RDDT", "PRDD"),
    "C1": ("PMNT", "IRCT", "ESCT"),
    "C2": ("PMNT", "RRCT", "ESCT"),
    "C3": ("PMNT", "IRCT", "RPCR"),
    "C4": ("PMNT", "RRCT", "RPCR"),
    "C5": ("PMNT", "IRCT", "RIMB"),
}
