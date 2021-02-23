"""""""""""""""""""""""""""""""""""""
" Plugin Management
"""""""""""""""""""""""""""""""""""""

call plug#begin()
  Plug 'preservim/nerdtree'
    nmap <silent> <F1> :call NERDTreeToggleInCurDir()<cr>

    function! NERDTreeToggleInCurDir()
      if (exists("t:NERDTreeBufName") && bufwinnr(t:NERDTreeBufName) != -1)
        exe ":NERDTreeClose"
      else
        exe ":NERDTreeFind"
      endif
    endfunction
    let g:golden_ratio_exclude_nonmodifiable = 1

  Plug 'numirias/semshi', {'do': ':UpdateRemotePlugins'}
  Plug 'Vimjas/vim-python-pep8-indent'
  Plug 'mattn/emmet-vim'
  Plug 'jiangmiao/auto-pairs'
  Plug 'phanviet/vim-monokai-pro'
  Plug 'tpope/vim-surround'
  Plug 'tpope/vim-repeat'
  Plug 'itchyny/lightline.vim'
  Plug 'tpope/vim-rails'
  Plug 'tpope/vim-fugitive'
  Plug 'vim-ruby/vim-ruby'
  Plug 'junegunn/fzf', { 'do': { -> fzf#install() } }
  Plug 'junegunn/fzf.vim'
  Plug 'tweekmonster/fzf-filemru'
  nnoremap <silent> <C-p> :FilesMru<CR>

  Plug 'tpope/vim-haml' 
  Plug 'tpope/vim-endwise'
  Plug 'rstacruz/vim-closer'
  Plug 'rhysd/vim-fixjson' 
  Plug 'Shougo/neosnippet.vim'
  Plug 'Shougo/neosnippet-snippets'
  Plug 'preservim/nerdcommenter'
  nmap <C-_> <leader>c<Space>
  nmap <C-_> <leader>_<Space>
  vmap <C-_> <leader>_<Space>
  
  Plug 'machakann/vim-highlightedyank'
  Plug 'roman/golden-ratio'
  " Easymotion
  Plug 'easymotion/vim-easymotion'
  " {{{
  let g:EasyMotion_do_mapping = 0
  let g:EasyMotion_smartcase = 1
  let g:EasyMotion_off_screen_search = 0
  nmap ; <Plug>(easymotion-s2)
" }}}
  Plug 'neoclide/coc.nvim', {'branch': 'master', 'do': 'yarn install --frozen-lockfile'}
  command! -nargs=0 Prettier :call CocAction('runCommand', 'prettier.formatFile')
  
call plug#end()


""""""""""""""""""""""""""""""""""""
" Line
""""""""""""""""""""""""""""""""""""
" show line numbers
set number
set wrap
set encoding=utf-8
set lazyredraw
set ruler
set laststatus=2
set visualbell
set textwidth=79
set backspace=indent,eol,start
set showtabline=2

" Move up/down editor lines
nnoremap j gj
nnoremap k gk
set hidden
set ttyfast
set laststatus=2
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

" when creating a new line, copy the indentation from the line above
set autoindent

"""""""""""""""""""""""""""""""""""""
" Search
"""""""""""""""""""""""""""""""""""""
" Ignore case when searching
set ignorecase
set smartcase
set incsearch
set hlsearch
nnoremap <CR> :nohlsearch<CR><CR>
set grepprg=rg\ --vimgrep\ --smart-case\ --follow
command! -bang -nargs=* Rg call fzf#vim#grep("rg --column --line-number --no-heading --color=always --smart-case ".shellescape(<q-args>), 1, {'options': '--delimiter : --nth 4..'}, <bang>0)

if has('nvim')
  " Enable live substitution
  set inccommand=split
endif


" highlight search results (after pressing Enter)
set hlsearch

" highlight all pattern matches WHILE typing the pattern
set incsearch

"""""""""""""""""""""""""""""""""""""
" Mix
"""""""""""""""""""""""""""""""""""""
" show the mathing brackets
set showmatch
set clipboard=unnamed

" highlight current line
set cursorline
set so=999

set termguicolors

colorscheme monokai_pro
set background=dark
set autoread

let g:lightline = {
      \ 'colorscheme': 'monokai_pro',
      \ }

filetype plugin on
filetype plugin indent on
syntax enable

noremap <Space> <Nop>
let mapleader=","
set iskeyword+=-

" set backup
set backupdir=~/.vim-tmp,~/.tmp,~/tmp,/var/tmp,/tmp
set backupskip=/tmp/*,/private/tmp/*
set directory=~/.vim-tmp,~/.tmp,~/tmp,/var/tmp,/tmp
set writebackup

" edit vimrc/zshrc and load vimrc bindings
nnoremap <leader>ev :vsp ~/.vimrc<CR>
nnoremap <leader>ez :vsp ~/.zshrc<CR>
nnoremap <leader>sv :source $MYVIMRC<CR>

