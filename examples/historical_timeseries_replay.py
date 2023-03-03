import databento as db
from databento import Bento


if __name__ == "__main__":
    db.log = "debug"  # Optional debug logging

    key = "YOUR_API_KEY"
    client = db.Historical(key=key)

    data: Bento = client.timeseries.get_range(
        dataset="GLBX.MDP3",
        symbols=["ESM2"],
        schema="trades",
        start="2022-06-10T12:00",
        end="2022-06-10T14:00",
        limit=1000,  # <-- Limiting response to 1000 records only
    )

    data.replay(callback=print)
