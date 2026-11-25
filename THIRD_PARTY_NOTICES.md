# Composants tiers

Le code de Guardian est publié sous la licence « sources consultables » de [LICENSE](LICENSE). Elle ne s'applique pas aux composants suivants, qui conservent leur propre licence.

## Embarqués dans le dépôt

| Composant | Fichiers | Licence |
| --- | --- | --- |
| Inter (Copyright 2016 The Inter Project Authors, https://github.com/rsms/inter) | `frontend/fonts/inter_01.woff2`, `frontend/fonts/inter_02.woff2` | SIL Open Font License 1.1 (https://openfontlicense.org), indiquée dans les métadonnées des polices |
| Police « Twemoji Mozilla » (twemoji-colr), version 0.7.0, https://github.com/mozilla/twemoji-colr | `frontend/fonts/Twemoji.woff2` | Code de la police : Apache License 2.0, Copyright 2016-2018 Mozilla Foundation. Dessins des émojis : Twemoji (https://github.com/twitter/twemoji), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Source d'après le mainteneur du projet ; les métadonnées du fichier n'indiquent que la version. |

## Dépendances Python incluses dans l'exécutable

Installées via `requirements.txt` et incluses dans l'exécutable compilé (versions de la compilation : psutil 7.2.2, pywebview 6.2.1, pycryptodome 4.6.0).

### psutil - BSD 3-Clause

Copyright (c) 2009, Jay Loden, Dave Daeschler, Giampaolo Rodola. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
* Neither the name of the psutil authors nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

### pywebview - BSD 3-Clause

Copyright (c) 2014-2017, Roman Sirokov. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
* Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

### PyCryptodome - domaine public (code issu de PyCrypto) et BSD 2-Clause

Une partie du code de PyCryptodome est dans le domaine public, le reste est sous licence BSD 2-Clause. Le copyright de chaque fichier appartient à son auteur respectif.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Le projet contient aussi du code de mldsa-native et mlkem-native (Apache-2.0, ISC ou MIT au choix) ; leurs textes figurent dans la distribution de PyCryptodome.

### Python et Nuitka

L'exécutable embarque l'interpréteur Python (licence PSF) et du code d'exécution Nuitka. Leurs mentions n'ont pas encore été vérifiées ni reproduites ici : voir https://docs.python.org/3/license.html et https://nuitka.net.

## Outil d'installation

L'installateur Windows est produit avec Inno Setup (https://jrsoftware.org/isinfo.php), qui n'est pas inclus dans le dépôt.
