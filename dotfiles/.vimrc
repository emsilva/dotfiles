""""""""""""""""""""""""""""""""""""""
" Plugin Management
"""""""""""""""""""""""""""""""""""""
if empty(glob('~/.vim/autoload/plug.vim'))
  silent !curl -fLo ~/.vim/autoload/plug.vim --create-dirs
    \ https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
  autocmd VimEnter * PlugInstall
endif

call plug#begin('~/.vim/plugged')

Plug 'vim-scripts/LargeFile'
Plug 'preservim/nerdtree'
nmap <silent> <F1> :call NERDTreeToggleInCurDir()<cr>
function! NERDTreeToggleInCurDir()
  if (exists("t:NERDTreeBufName") && bufwinnr(t:NERDTreeBufName) != -1)
  exe ":NERDTreeClose"
  else
  exe ":NERDTreeFind"
  endif
endfunction

Plug 'wellle/targets.vim'
Plug 'roman/golden-ratio'
Plug 'tpope/vim-vividchalk'
Plug 'dracula/vim', { 'as': 'dracula' }
Plug 'Rigellute/shades-of-purple.vim'
Plug 'jcherven/jummidark.vim'
Plug 'kyoz/purify', { 'rtp': 'vim' }
Plug 'lifepillar/vim-cheat40'
Plug 'ntpeters/vim-better-whitespace'
let g:strip_whitespace_on_save=1
let g:strip_whitespace_confirm=0

Plug 'tpope/vim-sensible'
Plug 'sheerun/vim-polyglot'
Plug 'jiangmiao/auto-pairs'
Plug 'tpope/vim-surround'
Plug 'tpope/vim-repeat'
Plug 'vim-airline/vim-airline'
Plug 'vim-airline/vim-airline-themes'

Plug 'tpope/vim-rails'
Plug 'tpope/vim-fugitive'
Plug 'vim-ruby/vim-ruby'
Plug 'junegunn/fzf', { 'do': { -> fzf#install() } }
Plug 'junegunn/fzf.vim'
Plug 'tweekmonster/fzf-filemru'

Plug 'tpope/vim-endwise'
Plug 'rhysd/vim-fixjson'
Plug 'Shougo/neosnippet.vim'
Plug 'Shougo/neosnippet-snippets'
Plug 'preservim/nerdcommenter'
nmap <C-_> <leader>c<Space>
Plug 'machakann/vim-highlightedyank'
Plug 'Chiel92/vim-autoformat'
Plug 'ap/vim-css-color'

call plug#end()

""""""""""""""""""""""""""""""""""""
" Plugin Configuration
""""""""""""""""""""""""""""""""""""
" Airline
if exists('g:loaded_airline')
  let g:airline_left_sep  = ''
  let g:airline_right_sep = ''
endif

" NeoSnippet
if exists('g:loaded_neosnippet')
  imap <C-k> <Plug>(neosnippet_expand_or_jump)
  smap <C-k> <Plug>(neosnippet_expand_or_jump)
  xmap <C-k> <Plug>(neosnippet_expand_target)
endif

" FZF
nnoremap <silent> <C-p> :FilesMru<CR>
nnoremap <leader>f :Files<CR>
nnoremap <leader>b :Buffers<CR>
nnoremap <leader>g :Rg<CR>
nnoremap <leader>h :History<CR>

""""""""""""""""""""""""""""""""""""
"   How it looks
""""""""""""""""""""""""""""""""""""
" Color Theme
colorscheme dracula
let g:terminal_ansi_colors = ['#132132', '#ff6a6f', '#a9dd9d', '#fedf81', '#7098e6', '#605779', '#a8d2eb', '#fffeeb', '#8d9eb2', '#fd8489', '#c9fd88', '#f0eaaa', '#98b8e6', '#e7d5ff', '#a8d2eb', '#ffffff']

set number
set nowrap
set encoding=utf-8
set lazyredraw
set ruler
set laststatus=2
set visualbell
set wildmenu
set wildmode=list:longest,full
set scrolloff=3
set sidescrolloff=5
set history=1000
set undolevels=1000
set textwidth=79
set backspace=indent,eol,start
set showtabline=2
set colorcolumn=80
if (has("termguicolors"))
  set termguicolors
  set t_8f=[38;2;%lu;%lu;%lum
  set t_8b=[48;2;%lu;%lu;%lum
endif

" Security & Performance
set modelines=0
set secure
set updatetime=250
set timeoutlen=500

" Backup/Swap file handling
set nobackup
set nowritebackup
set noswapfile

""""""""""""""""""""""""""""""""""""
" Line
""""""""""""""""""""""""""""""""""""
" show line numbers
set noerrorbells visualbell
set ve+=onemore
set mouse+=a

" Move up/down editor lines
nnoremap j gj
nnoremap k gk
set hidden
set ttyfast
set showmode
set showcmd
"""""""""""""""""""""""""""""""""""""
" Indents
"""""""""""""""""""""""""""""""""""""
" replace tabs with spaces
set expandtab
" 1 tab = 2 spaces
set tabstop=2 shiftwidth=2

" when deleting whitespace at the beginning of a line, delete
" 1 tab worth of spaces (for us this is 2 spaces)
set smarttab
set smartindent

" when creating a new line, copy the indentation from the line above
set autoindent


set splitbelow  " open a new horizontal split below
set splitright  " open a new horizontal split on the right


set fillchars=vert:│  " Vertical separator between windows"
nnoremap <C-h> <C-w>h " Ctrl + h to move to the left split
nnoremap <C-l> <C-w>l " Ctrl + l to move to the right one

"""""""""""""""""""""""""""""""""""""
" Search
"""""""""""""""""""""""""""""""""""""
" Ignore case when searching
set ignorecase
set smartcase
set incsearch
set hlsearch
nnoremap <leader><space> :nohlsearch<CR>
set grepprg=rg\ --vimgrep\ --smart-case\ --follow
command! -bang -nargs=* Rg call fzf#vim#grep("rg --column --line-number --no-heading --color=always --smart-case ".shellescape(<q-args>), 1, {'options': '--delimiter : --nth 4..'}, <bang>0)

if has('nvim')
  " Enable live substitution
  set inccommand=split
endif

"""""""""""""""""""""""""""""""""""""
" Mix
"""""""""""""""""""""""""""""""""""""
" show the matching brackets
set showmatch
set clipboard=unnamed

set autoread

filetype plugin on
filetype plugin indent on

noremap <Space> <Nop>
let mapleader=","
set iskeyword+=-

if empty($TMUX)
  let &t_SI = "\<Esc>]50;CursorShape=1\x7"
  let &t_EI = "\<Esc>]50;CursorShape=0\x7"
  let &t_SR = "\<Esc>]50;CursorShape=2\x7"
else
  let &t_SI = "\<Esc>Ptmux;\<Esc>\<Esc>]50;CursorShape=1\x7\<Esc>\\"
  let &t_EI = "\<Esc>Ptmux;\<Esc>\<Esc>]50;CursorShape=0\x7\<Esc>\\"
  let &t_SR = "\<Esc>Ptmux;\<Esc>\<Esc>]50;CursorShape=2\x7\<Esc>\\"
endif


" edit vimrc/zshrc and load vimrc bindings
nnoremap <leader>ev :vsp ~/.vimrc<CR>
nnoremap <leader>ez :vsp ~/.zshrc<CR>
nnoremap <leader>sv :source $MYVIMRC<CR>
noremap <F3> :Autoformat<CR>

