import multiprocessing.dummy as mp


def do_print(s):
    print(s)


if __name__ == "__main__":
    p = mp.Pool(4)
    p.map(do_print, range(0, 1000))  # range(0,1000) if you want to replicate your example
    p.close()
    p.join()
