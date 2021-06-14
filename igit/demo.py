
import random
from .repo import Repo

def demo_repo(path="memory://igit_demo"):
    r = Repo.init(path)

    c = r.new_config_group("config")
    to_pe = c.new_interval_group("to_pe")
    to_pe[1,10] = 11
    to_pe[10,100] = 20
    gains = c.new_interval_group("gains")
    gains[1,10] = [1,2,3,4]
    gains[5,30] = [4,3,2,1]
    gains[30,200] = [1,1,1,1]

    run_id = c.new_interval_group("run_id")
    times = range(0,200, 15)
    for i, period in enumerate(zip(times[:-1], times[1:])):
        run_id[period] = f"run{i:04}"
    r.new_interval_group("intervals")
    r.new_label_group("labels")
    r.labels.new_interval_group("intervals")
    r.labels.new_interval_group("intervals2")
    r.intervals[1,10] = 9
    r.intervals[9,20] = 11
    r.intervals.new_label_group((20,25))
    r.labels.intervals[9,100] = 78
    r.labels.intervals[9,100] = 12
    r.intervals[20,25]["setting5"] = 9
    r.labels["setting3"] = "text"
    r.labels["setting4"] = "A very long text field to show how long values are cut short in the tree view"

    c = r.new_config_group("calibrations")
    ambe = c.new_interval_group("ambe")
    ambe[1,10] = {"daq_settings": {}, "comments": []}
    ambe[10,100] = {"daq_settings": {}, "comments": []}
    rn220 = c.new_interval_group("rn220")
    rn220[1,10] = {"daq_settings": {}, "comments": []}
    rn220[5,30] = {"daq_settings": {}, "comments": []}
    rn220[30,200] = {"daq_settings": {}, "comments": []}

    r.igit.add()
    r.igit.commit(f"commit {random.randint(1,10)}")
    r.labels["subsetting7"] = 9
    r.igit.add()
    r.igit.commit(f"second commit {random.randint(20,30)}")
    r.igit.checkout("new_branch", branch=True)
    r.labels["subsetting7"] = 10
    r.igit.add()
    ref = r.igit.commit(f"branch commit {random.randint(20,30)}")
    r.igit.checkout("master")
    r.labels["subsetting8"] = 110
    r.igit.add()
    ref = r.igit.commit(f"branch commit {random.randint(20,30)}")
    r.igit.tag("test_tag")
    r.save()
    return r