
make venv
add flask
flask run --host=0.0.0.0 --port=5000

need to open port on linux machine

iptables -A INPUT -p tcp --match multiport --dports 5000:5100 -j ACCEPT
