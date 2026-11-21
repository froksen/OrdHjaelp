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
