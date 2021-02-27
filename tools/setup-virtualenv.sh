#!/bin/sh -e

# install woob inside a virtualenv, optionally with an associated woob workdir
# can be combined with git-worktree

cd "$(dirname $0)/.."
SRC=$PWD

source=
VDIR=

usage () {
    cat << EOF
Usage: $0 [-s] [-d DIR]
  -s            point sources.list to $SRC/modules instead of updates.woob.tech
  -d DIR        install virtualenv in DIR instead of a new dir
EOF
}

while getopts hsd: name
do
    case $name in
    s) source=y;;
    d) VDIR="$OPTARG";;
    h) usage
       exit 0;;
    ?) usage
       exit 2;;
    esac
done
shift $(($OPTIND - 1))

PYTHON=${PYTHON-python3}

echo "Using woob source $SRC"

if [ -z "$VDIR" ]
then
    VDIR=$(mktemp -d /tmp/woob.venv.XXXXXX)
fi

cd "$VDIR"
echo "Creating env in $VDIR"

virtualenv -p "$(which "$PYTHON")" --system-site-packages "$VDIR"
. ./bin/activate

echo "Installing woob in $VDIR"
"$PYTHON" -m pip install "$SRC"

mkdir workdir
export WOOB_WORKDIR=$VDIR/workdir

if [ "$source" = y ]
then
    echo "file://$SRC/modules" > "$WOOB_WORKDIR/sources.list"
fi

cat > use-woob-local.sh << EOF
VDIR="$VDIR"
. "$VDIR/bin/activate"
export WOOB_WORKDIR="$VDIR/workdir"
EOF

cat << EOF
Installation complete in $VDIR.
Run ". $VDIR/use-woob-local.sh" to start using it.
Run "$PYTHON -m pip install -U $SRC" to reinstall the core.
EOF

if [ "$source" != y ]
then
    echo "You can add file://$SRC/modules into $VDIR/workdir/sources.list to use local modules instead of downloading modules."
fi

./bin/woob config update
