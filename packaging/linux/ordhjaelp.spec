# RPM for Ordhjælp. Bygges af packaging/linux/build-rpm.sh – ikke direkte.
#
# Ordhjælp medbringer sin egen Python 3.13 med alle Python-pakker i /opt/ordhjaelp,
# fordi flere af dem (piper-tts, faster-whisper, onnxruntime) ikke findes i Fedora.
# Systemværktøjer hentes som almindelige Fedora-pakker (Requires nedenfor).

%global debug_package %{nil}
%global __os_install_post %{nil}
%global _build_id_links none

Name:           ordhjaelp
Version:        %{ordhjaelp_version}
Release:        1%{?dist}
Summary:        Dansk læse- og skrivehjælp: oplæsning, diktering og ordforslag
License:        GPL-3.0-or-later
BuildArch:      x86_64
# Den medbragte Python skal ikke give automatiske afhængigheder
AutoReqProv:    no

Requires:       wl-clipboard
Requires:       portaudio
Requires:       tesseract
Requires:       tesseract-langpack-dan
Requires:       hunspell
Requires:       hunspell-da
Requires:       ibus
Requires:       ibus-panel
Requires:       python3-gobject
Requires:       xdg-desktop-portal
# Læs under musen: tilgængelighedsbussen (Wayland og X11) og musens position på X11
Requires:       at-spi2-core
Recommends:     xdotool
# Hjælp til opsætning af ordforslag på KDE: læs valgt virtuelt tastatur, åbn indstillingssiden
Recommends:     kf6-kconfig
Recommends:     kf6-kcmutils

%description
Ordhjælp er et gratis læse- og skriveværktøj (LST) til danske elever.
Det kører offline og kan læse markeret tekst op, skrive det, man siger
(diktering), læse tekst fra skærmen og give ordforslag – også når ord
staves lydret. Stemme og talegenkendelse hentes første gang, programmet starter.

%install
cp -a %{stage}/. %{buildroot}/

%files
/opt/ordhjaelp
%{_bindir}/ordhjaelp
%{_datadir}/applications/dk.ordhjaelp.Ordhjaelp.desktop
%{_datadir}/icons/hicolor/scalable/apps/dk.ordhjaelp.Ordhjaelp.svg

%post
/usr/bin/gtk-update-icon-cache -q %{_datadir}/icons/hicolor &>/dev/null || :

%postun
/usr/bin/gtk-update-icon-cache -q %{_datadir}/icons/hicolor &>/dev/null || :

%changelog
* Sat Nov 21 2026 Ole Frandsen - 0.2.0-1
- Hjælp til opsætning af ordforslag: vejledning og statustjek i indstillingerne
- Læs ordet/sætningen op mens du skriver virker nu også uden ordforslag
- Markeret tekst i LibreOffice Writer på Wayland læses via AT-SPI
- Læs ved markering og læs under musen (bidrag fra qvisty)
- Velkomstvindue: vælg og hent sprogmodeller; administration i indstillingerne
- Første udgave af Windows-understøttelse (bidrag fra qvisty)

* Sat Nov 21 2026 Ole Frandsen - 0.1.0-1
- Første udgave
