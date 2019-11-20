from __future__ import unicode_literals
from flask_superadmin.contrib import DeprecatedModelView

from flask_superadmin.model.backends.django import ModelAdmin


class ModelView(DeprecatedModelView, ModelAdmin):
    pass
