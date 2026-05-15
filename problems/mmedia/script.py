import os

os.mkdir("instances")

instances = ""
inputFile = ""

for i in os.listdir(os.getcwd()):
    if not i.startswith("script") and not os.path.isdir(i):
        exec(open(i).read())
        with open(f"instances/{i}.lp", "w") as f:
            f.write(input)
        instances += f"{i}.lp\n"
        inputFile += f"<load \"problems/mmedia/{i}.lp\" />\n<run />\n"

with open("instances.list", "w") as f:
    f.write(instances)

with open("input.xml", "w") as f:
    f.write(inputFile)
