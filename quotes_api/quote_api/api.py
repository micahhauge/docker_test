import datetime, time

from flask import Flask, jsonify, request
from flask_restful import Resource, Api
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from sqlalchemy_utils import database_exists
from marshmallow import Schema, fields, ValidationError, pre_load

app = Flask(__name__)

# create a restful api
api = Api(app)

# configure postgres settings
POSTGRES = {
    'user': 'postgres',
    'pw': '',
    'db': 'postgres',
    'host': 'db',
    'port': '5432',
}
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://%(user)s:\%(pw)s@%(host)s:%(port)s/%(db)s' % POSTGRES

# wait for db
while (True):
    try:
        database_exists(app.config['SQLALCHEMY_DATABASE_URI'])
        print("Connection to database successful!")
        break

    except Exception as e:
        # print('Connection to DB Failed. Attempting to reconnect in 5 seconds...')
        time.sleep(.5)

db = SQLAlchemy(app)

##### MODELS #####

class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first = db.Column(db.String(80))
    last = db.Column(db.String(80))

class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("author.id"))
    author = db.relationship("Author",
                        backref=db.backref("quotes", lazy="dynamic"))
    posted_at = db.Column(db.DateTime)

##### SCHEMAS #####

class AuthorSchema(Schema):
    id = fields.Int(dump_only=True)
    first = fields.Str()
    last = fields.Str()
    formatted_name = fields.Method("format_name", dump_only=True)

    def format_name(self, author):
        return "{}, {}".format(author.last, author.first)


# Custom validator
def must_not_be_blank(data):
    if not data:
        raise ValidationError('Data not provided.')

class QuoteSchema(Schema):
    id = fields.Int(dump_only=True)
    author = fields.Nested(AuthorSchema, validate=must_not_be_blank)
    content = fields.Str(required=True, validate=must_not_be_blank)
    posted_at = fields.DateTime(dump_only=True)

    # Allow client to pass author's full name in request body
    # e.g. {"author': 'Tim Peters"} rather than {"first": "Tim", "last": "Peters"}
    @pre_load
    def process_author(self, data):
        author_name = data.get('author')
        if author_name:
            first, last = author_name.split(' ')
            author_dict = dict(first=first, last=last)
        else:
            author_dict = {}
        data['author'] = author_dict
        return data

author_schema = AuthorSchema()
authors_schema = AuthorSchema(many=True)
quote_schema = QuoteSchema()
quotes_schema = QuoteSchema(many=True, only=('id', 'content'))

##### API #####
# define course service
class Course(Resource):
    def get(self):
        return {
            "hi": "hi"
        }

# add product service to restful api
api.add_resource(Course, '/')






@app.route('/')
def hello():
    return jsonify({'hi': 'hi'})

@app.route('/authors')
def get_authors():
    authors = Author.query.all()
    # Serialize the queryset
    result = authors_schema.dump(authors)
    return jsonify({'authors': result.data})

@app.route("/authors/<int:pk>")
def get_author(pk):
    try:
        author = Author.query.get(pk)
    except IntegrityError:
        return jsonify({"message": "Author could not be found."}), 400
    author_result = author_schema.dump(author)
    quotes_result = quotes_schema.dump(author.quotes.all())
    return jsonify({'author': author_result.data, 'quotes': quotes_result.data})

@app.route('/quotes/', methods=['GET'])
def get_quotes():
    quotes = Quote.query.all()
    result = quotes_schema.dump(quotes)
    return jsonify({"quotes": result.data})

@app.route("/quotes/<int:pk>")
def get_quote(pk):
    try:
        quote = Quote.query.get(pk)
    except IntegrityError:
        return jsonify({"message": "Quote could not be found."}), 400
    result = quote_schema.dump(quote)
    return jsonify({"quote": result.data})

@app.route("/quotes/", methods=["POST"])
def new_quote():
    json_data = request.get_json()
    if not json_data:
        return jsonify({'message': 'No input data provided'}), 400
    # Validate and deserialize input
    data, errors = quote_schema.load(json_data)
    if errors:
        return jsonify(errors), 422
    first, last = data['author']['first'], data['author']['last']
    author = Author.query.filter_by(first=first, last=last).first()
    if author is None:
        # Create a new author
        author = Author(first=first, last=last)
        db.session.add(author)
    # Create new quote
    quote = Quote(
        content=data['content'],
        author=author,
        posted_at=datetime.datetime.utcnow()
    )
    db.session.add(quote)
    db.session.commit()
    result = quote_schema.dump(Quote.query.get(quote.id))
    return jsonify({"message": "Created new quote.",
                    "quote": result.data})

if __name__ == '__main__':
    db.create_all()
    print('running on port 5001')
    app.run(host='0.0.0.0', port=5001, debug=True)
