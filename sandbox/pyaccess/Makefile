# Makefile
#
# Based in a part on Makefile from vlc in ccnx distribution
# which is based on x264 plugin Makefile
#

libdir := $(shell pkg-config --variable=libdir vlc-plugin)
vlclibdir := $(libdir)/vlc

vlcplugindir := $(shell pkg-config --atleast-version=1.1.0 vlc-plugin && echo /plugins)
VLCPLUGINVERDEF := $(shell pkg-config --modversion vlc-plugin | sed 's/\(^.....\).*/-DVLCPLUGINVER=\1/;s/\.//g;s/=0/=/')

plugin_name=libaccess_python_plugin
plugin_access_out=libaccess_output_python_plugin
python_inc=-I/usr/include/python2.7
CFLAGS=-ggdb3 -O0 -Wall -std=gnu99  $< `pkg-config --cflags vlc-plugin` $(python_inc)
LDFLAGS=-Wall
LIBS=-lpython2.7

all: $(plugin_name).so $(plugin_access_out).so

$(plugin_name).so: $(plugin_name).o
	gcc -g -shared -std=gnu99 $(LDFLAGS) $< `pkg-config --libs vlc-plugin` -Wl,-soname -Wl,$@ $(LIBS) -o $@

$(plugin_name).o: $(plugin_name).c
	gcc -c -fPIC $(CFLAGS) -D__PLUGIN__  -DMODULE_STRING=\"python\" $(VLCPLUGINVERDEF) -o $@

$(plugin_access_out).so: $(plugin_access_out).o
	gcc -g -shared -std=gnu99 $(LDFLAGS) $< `pkg-config --libs vlc-plugin` -Wl,-soname -Wl,$@ $(LIBS) -o $@

$(plugin_access_out).o: $(plugin_access_out).c
	gcc -c -fPIC $(CFLAGS) -D__PLUGIN__  -DMODULE_STRING=\"python\" $(VLCPLUGINVERDEF) -o $@

clean:
	rm -f $(plugin_name).[o,so] $(plugin_access_out).[o,so]

install: all
	mkdir -p $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access/
	install -m 0755 $(plugin_name).so $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access/
	mkdir -p $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access_output/
	install -m 0755 $(plugin_access_out).so $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access_output/

install-strip: all
	mkdir -p $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access/
	install -s -m 0755 $(plugin_name).so $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access/
	mkdir -p $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access_output/
	install -s -m 0755 $(plugin_access_out).so $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access_output/

uninstall:
	rm -f -- $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access/$(plugin_name).so
	rm -f -- $(DESTDIR)$(vlclibdir)$(vlcplugindir)/access_output/$(plugin_access_out).so

.PHONY: all clean install uninstall
