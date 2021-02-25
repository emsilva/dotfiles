path() {
  echo $PATH | tr : '\n'
}

gg() {
  git commit -a -m "$@"
}

cdmk() {
    mkdir "$1" && cd "$1"
}
