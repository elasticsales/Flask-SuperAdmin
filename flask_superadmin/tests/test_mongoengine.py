from nose.tools import eq_, ok_, raises

from flask import Flask
from flask.ext import wtf
from mongoengine import *

from flask_superadmin import Admin
from flask_superadmin.model.backends.mongoengine.view import ModelAdmin


class CustomModelView(ModelAdmin):
    def __init__(self, model, name=None, category=None, endpoint=None,
                 url=None, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)

        super(CustomModelView, self).__init__(model, name, category, endpoint,
                                              url)


def setup():
    connect('superadmin_test')
    app = Flask(__name__)
    app.config['SECRET_KEY'] = '1'
    app.config['CSRF_ENABLED'] = False

    admin = Admin(app)

    return app, admin


def test_model():
    app, admin = setup()

    class Person(Document):
        name = StringField()
        age = IntField()

    Person.drop_collection()

    view = CustomModelView(Person)
    admin.add_view(view)

    eq_(view.model, Person)
    eq_(view.name, 'Person')
    eq_(view.endpoint, 'person')
    eq_(view.url, '/admin/person')

    # Verify form
    with app.test_request_context():
        Form = view.get_form()
        ok_(isinstance(Form()._fields['name'], wtf.TextAreaField))
        ok_(isinstance(Form()._fields['age'], wtf.IntegerField))

    # Make some test clients
    client = app.test_client()

    resp = client.get('/admin/person/')
    eq_(resp.status_code, 200)

    resp = client.get('/admin/person/add/')
    eq_(resp.status_code, 200)

    resp = client.post('/admin/person/add/',
                     data=dict(name='name', age='18'))
    eq_(resp.status_code, 302)

    person = Person.objects.first()
    eq_(person.name, 'name')
    eq_(person.age, 18)

    resp = client.get('/admin/person/')
    eq_(resp.status_code, 200)
    ok_(str(person.pk) in resp.data)

    resp = client.get('/admin/person/%s/' % person.pk)
    eq_(resp.status_code, 200)

    resp = client.post('/admin/person/%s/' % person.pk, data=dict(name='changed'))
    eq_(resp.status_code, 302)

    person = Person.objects.first()
    eq_(person.name, 'changed')
    eq_(person.age, 18)

    resp = client.post('/admin/person/%s/delete/' % person.pk)
    eq_(resp.status_code, 200)
    eq_(Person.objects.count(), 1)

    resp = client.post('/admin/person/%s/delete/' % person.pk, data={'confirm_delete': True})
    eq_(resp.status_code, 302)
    eq_(Person.objects.count(), 0)


def test_list_display():
    app, admin = setup()

    class Person(Document):
        name = StringField()
        age = IntField()

    Person.drop_collection()

    view = CustomModelView(Person, list_display=('name', 'age'))
    admin.add_view(view)

    eq_(len(view.list_display), 2)

    client = app.test_client()

    resp = client.get('/admin/person/')
    ok_('Name' in resp.data)
    ok_('Age' in resp.data)

    resp = client.post('/admin/person/add/',
                     data=dict(name='Steve', age='18'))
    eq_(resp.status_code, 302)

    resp = client.get('/admin/person/')
    ok_('Steve' in resp.data)
    ok_('18' in resp.data)


def test_exclude():
    app, admin = setup()

    class Person(Document):
        name = StringField()
        age = IntField()

    Person.drop_collection()

    view = CustomModelView(Person, exclude=['name'])
    admin.add_view(view)

    # Verify form
    with app.test_request_context():
        Form = view.get_form()
        eq_(sorted(Form()._fields.keys()), ['age', 'csrf_token'])

def test_fields():
    app, admin = setup()

    class Person(Document):
        name = StringField()
        age = IntField()

    Person.drop_collection()
    fields = ['name']
    view = CustomModelView(Person, fields=fields)
    admin.add_view(view)

    # Verify form
    with app.test_request_context():
        Form = view.get_form()
        eq_(view.fields, fields)
        eq_(sorted(Form()._fields.keys()), ['age', 'csrf_token', 'name'])

def test_fields_and_exclude():
    app, admin = setup()

    class Person(Document):
        name = StringField()
        age = IntField()

    Person.drop_collection()

    view = CustomModelView(Person, fields=['name', 'age'], exclude=['name'])
    admin.add_view(view)

    # Verify form
    with app.test_request_context():
        Form = view.get_form()
        eq_(sorted(Form()._fields.keys()), ['age', 'csrf_token'])

def test_search_fields():
    app, admin = setup()

    class Person(Document):
        name = StringField()
        age = IntField()

    Person.drop_collection()
    Person.objects.create(name='John', age=18)
    Person.objects.create(name='Michael', age=21)

    view = CustomModelView(Person, list_display=['name'],
                           search_fields=['name'])
    admin.add_view(view)

    eq_(len(view.search_fields), 1)
    client = app.test_client()

    resp = client.get('/admin/person/')
    ok_('name="q" class="search-input"' in resp.data)
    ok_('John' in resp.data)
    ok_('Michael' in resp.data)

    resp = client.get('/admin/person/?q=john')
    ok_('John' in resp.data)
    ok_('Michael' not in resp.data)


def test_pagination():
    app, admin = setup()

    class Person(Document):
        name = StringField()
        age = IntField()

    Person.drop_collection()
    Person.objects.create(name='John', age=18)
    Person.objects.create(name='Michael', age=21)
    Person.objects.create(name='Steve', age=15)
    Person.objects.create(name='Ron', age=59)

    view = CustomModelView(Person, list_per_page=2,
                           list_display=['name', 'age'])
    admin.add_view(view)

    client = app.test_client()

    resp = client.get('/admin/person/')
    ok_('<div class="total-count">Total count: 4</div>' in resp.data)
    ok_('<a href="#">1</a>' in resp.data)  # make sure the first page is active (i.e. has no url)
    ok_('John' in resp.data)
    ok_('Michael' in resp.data)
    ok_('Steve' not in resp.data)
    ok_('Ron' not in resp.data)

    # default page == page 0
    eq_(resp.data, client.get('/admin/person/?page=0').data)

    resp = client.get('/admin/person/?page=1')
    ok_('John' not in resp.data)
    ok_('Michael' not in resp.data)
    ok_('Steve' in resp.data)
    ok_('Ron' in resp.data)

def test_sort():
    app, admin = setup()

    class Person(Document):
        name = StringField()
        age = IntField()

    Person.drop_collection()
    Person.objects.create(name='John', age=18)
    Person.objects.create(name='Michael', age=21)
    Person.objects.create(name='Steve', age=15)
    Person.objects.create(name='Ron', age=59)

    view = CustomModelView(Person, list_per_page=2,
                           list_display=['name', 'age'])
    admin.add_view(view)

    client = app.test_client()

    resp = client.get('/admin/person/?sort=name')
    ok_('John' in resp.data)
    ok_('Michael' in resp.data)
    ok_('Ron' not in resp.data)
    ok_('Steve' not in resp.data)

    resp = client.get('/admin/person/?sort=-name')
    ok_('John' not in resp.data)
    ok_('Michael' not in resp.data)
    ok_('Ron' in resp.data)
    ok_('Steve' in resp.data)

    resp = client.get('/admin/person/?sort=age')
    ok_('John' in resp.data)
    ok_('Michael' not in resp.data)
    ok_('Ron' not in resp.data)
    ok_('Steve' in resp.data)

    resp = client.get('/admin/person/?sort=-age')
    ok_('John' not in resp.data)
    ok_('Michael' in resp.data)
    ok_('Ron' in resp.data)
    ok_('Steve' not in resp.data)

