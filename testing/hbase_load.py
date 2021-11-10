"""
Description: This scripts insert data into HBase.
Author: Humberto Galiza
Date: 03 November 2021
Original data source:
    - https://s3.amazonaws.com/tripdata/202110-citibike-tripdata.csv.zip

To create the table, first use the hbase shell. We are going to create a
namespace called "sample_data". The table for this script is called "tripdata",
as we will be inserting bike trip data from the City of New York.

Our table will have three column families:
    - "ride_data", to store generic ride info
    - "time_data", to store time related info
    - "geo_data", to store geospatial info

For all we are accepting all table defaults.

% hbase shell (or 'docker exec -it hbase-docker hbase shell' if running hbase from docker)
hbase> create_namespace "sample_data"
hbase> create "sample_data:tripdata", "ride_data", "time_data", "geo_data"
"""

import csv
import happybase
import time
import json
import logging
import statistics

# batch_size = 5000
host = "127.0.0.1"
port = 55038
file_path = "xaa"
namespace = "sample_data"
table_name = "tripdata"
BATCHES = [100, 1000, 2000, 5000, 10000, 50000, 100000, 200000]
REPETITION = 20


def connect_to_hbase(batch_size):
    """
    Connect to HBase server.
    This will use the host, namespace, table name, and batch size as defined in
    the global variables above.
    """
    conn = happybase.Connection(
        host=host, port=port, table_prefix=namespace, table_prefix_separator=":"
    )
    conn.open()
    try:
        # delete previous run, to avoid influence of disk space/number of records in the measurements
        conn.disable_table(table_name)
        conn.delete_table(table_name)
    except Exception as error:
        logging.warning(f"Couldn't disable table {table_name}, error: {error}")
        pass
    # create the new table under the namespace
    conn.create_table(
        table_name, {"ride_data": dict(), "time_data": dict(), "geo_data": dict()}
    )
    table = conn.table(table_name)
    batch = table.batch(batch_size=batch_size)
    return conn, batch


def insert_row(batch, row):
    """
    Insert a row into HBase.
    Write the row to the batch. When the batch size is reached, rows will be
    sent to the database.
    Rows have the following schema:
        [ ride_id, rideable_type, started_at, ended_at, start_station_name, start_station_id,
        end_station_name, end_station_id, start_lat, start_lng, end_lat, end_lng, member_casual ]
    """
    batch.put(
        row[0],
        {
            "ride_data:ride_type": row[1],
            "ride_data:started_at": row[2],
            "ride_data:ended_at": row[3],
            "ride_data:start_station_name": row[4],
            "ride_data:start_station_id": row[5],
            "ride_data:end_station_name": row[6],
            "ride_data:end_station_id": row[7],
            "ride_data:member_casual": row[12],
            "geo_data:start_lat": row[8],
            "geo_data:start_lng": row[9],
            "geo_data:end_lat": row[10],
            "geo_data:end_lng": row[11],
        },
    )


def read_csv():
    csvfile = open(file_path, "r")
    csvreader = csv.reader(csvfile)
    return csvreader, csvfile


result = {}

for batch_size in BATCHES:
    result[batch_size] = {}
    result[batch_size]["mean"] = 0
    result[batch_size]["median"] = 0
    result[batch_size]["stdev"] = 0
    total_tmp = []
    for i in range(1, REPETITION + 1):
        row_count = 0
        start_time = time.time()
        # After everything has been defined, run the script.
        conn, batch = connect_to_hbase(batch_size)
        print(f"Starting execution {i} for batch_size: {batch_size}")
        csvreader, csvfile = read_csv()
        # Loop through the rows. The first row contains column headers, so skip that
        # row. Insert all remaining rows into the database.
        for row in csvreader:
            row_count += 1
            if row_count == 1:
                pass
            else:
                insert_row(batch, row)
        # If there are any leftover rows in the batch, send them now.
        batch.send()
        csvfile.close()
        conn.close()
        duration = time.time() - start_time
        total_tmp.append(duration)
        print(
            f"Finished execution {i} for batch_size: {batch_size}. Inserted row count: {row_count}, duration: {duration}"
        )
        print(f"Partial stats")
        print(f"Mean (partial): {statistics.mean(total_tmp)}")
        if i > 1:
            print(f"Stdev (partial): {statistics.stdev(total_tmp)}")
        print(f"Median (partial): {statistics.median(total_tmp)}")
    result[batch_size]["mean"] = statistics.mean(total_tmp)
    result[batch_size]["median"] = statistics.median(total_tmp)
    result[batch_size]["stdev"] = statistics.stdev(total_tmp)
    print("===" * 40)
    print(
        f"Simulation ended for batch_size {batch_size}.\nResults:\n{result[batch_size]}"
    )
    print("===" * 40)
print("*" * 79)
print(f"Simulation ended.\nResults: {result}")
out_file = open("simulation_result.json", "w")
json.dump(result, out_file, indent = 6)
out_file.close()
