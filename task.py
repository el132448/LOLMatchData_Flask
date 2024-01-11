import requests

def update():
    response = requests.get('https://el132448.pythonanywhere.com/panel/update/')
    print(response)

if __name__ == '__main__':
    update()