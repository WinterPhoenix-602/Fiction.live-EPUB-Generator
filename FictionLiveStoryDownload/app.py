import os
from flask import Flask, render_template, request
from FictionLiveAPI import main

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        story_urls = request.form['story_urls']
        try:
            main(story_urls)
            message = 'EPUB file(s) created successfully!'
        except Exception as e:
            message = f'Error: {str(e)}'

        return render_template('index.html', message=message)

    return render_template('index.html', message=None)

if __name__ == '__main__':
    app.run(debug=True)
