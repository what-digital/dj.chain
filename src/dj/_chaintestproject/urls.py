# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()
from aldryn_addons.urls import patterns

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', '_chaintestproject.views.home', name='home'),
    # url(r'^_chaintestproject/', include('_chaintestproject.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
)
