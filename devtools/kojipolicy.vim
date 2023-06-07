" Vim syntax file
" Language:	koji policy
" Maintainer:	Tomas Kopecek <tkopecek@redhat.com>
" Last Change:	2023 June 6
"
" It is limited experimental/incomplete syntax highlighting file
" for koji policies (hub/gc)

" Quit when a (custom) syntax file was already loaded
if exists("b:current_syntax")
  finish
endif

" policy.py
syn keyword kojiPolicyTest has bool match target compare true false all none 

" kojihub.py
syn keyword kojiPolicyTest package version release is_new_package
syn keyword kojiPolicyTest tag fromtag hastag skip_tag skip_tag buildtag buildtag_inherits_from
syn keyword kojiPolicyTest cg_match_any cg_match_all
syn keyword kojiPolicyTest volume vm_name
syn keyword kojiPolicyTest user is_build_owner user_in_group has_perm
syn keyword kojiPolicyTest buildtype imported source 
syn keyword kojiPolicyTest policy operation method is_child_task

" plugins
syn keyword kojiPolicyTest is_sidetag is_sidetag_owner

" internal
syn keyword kojiPolicyTest match_any match_all sigkey

syn keyword kojiPolicyAction allow deny use yes no

syn keyword kojiPolicyPolicy build_from_scm build_from_srpm build_from_repo_id
syn keyword kojiPolicyPolicy package_list channel volume prep_kerberos sidetag
syn keyword kojiPolicyPolicy priority scm cg_import

syn keyword kojiPolicyTodo contained TODO FIXME XXX

syn match   kojiPolicyComment  "^#.*" contains=confTodo,@Spell
syn match   kojiPolicyComment  "\s#.*"ms=s+1 contains=confTodo,@Spell
syn match   kojiPolicyString   /[a-zA-Z0-9_\-\[\]\.\?\*\/]\+/
syn match   kojiPolicyOperator "::"
syn match   kojiPolicyOperator "&&"
syn match   kojiPolicyOperator "!!"
syn match   kojiPolicyValue    "target"
syn match   kojiPolicyValue    "scratch"
syn match   kojiPolicyValue    "scm_scheme"
syn match   kojiPolicyValue    "scm_repository"
syn match   kojiPolicyValue    "scm_type"
syn match   kojiPolicyValue    "scm_host"
syn match   kojiPolicyValue    "source"
syn match   kojiPolicyValue    "branches"

syn match   kojiPolicyValue    "appliance"
syn match   kojiPolicyValue    "build"
syn match   kojiPolicyValue    "buildArch"
syn match   kojiPolicyValue    "buildMaven"
syn match   kojiPolicyValue    "buildNotification"
syn match   kojiPolicyValue    "buildSRPMFromSCM"
syn match   kojiPolicyValue    "chainbuild"
syn match   kojiPolicyValue    "chainmaven"
syn match   kojiPolicyValue    "createAppliance"
syn match   kojiPolicyValue    "createDudIso"
syn match   kojiPolicyValue    "createImage"
syn match   kojiPolicyValue    "createKiwiImage"
syn match   kojiPolicyValue    "createLiveCD"
syn match   kojiPolicyValue    "createLiveMedia"
syn match   kojiPolicyValue    "createdistrepo"
syn match   kojiPolicyValue    "createrepo"
syn match   kojiPolicyValue    "default"
syn match   kojiPolicyValue    "dependantTask"
syn match   kojiPolicyValue    "distRepo"
syn match   kojiPolicyValue    "dudBuild"
syn match   kojiPolicyValue    "fork"
syn match   kojiPolicyValue    "image"
syn match   kojiPolicyValue    "indirectionimage"
syn match   kojiPolicyValue    "kiwiBuild"
syn match   kojiPolicyValue    "livecd"
syn match   kojiPolicyValue    "livemedia"
syn match   kojiPolicyValue    "maven"
syn match   kojiPolicyValue    "newRepo"
syn match   kojiPolicyValue    "rebuildSRPM"
syn match   kojiPolicyValue    "restart"
syn match   kojiPolicyValue    "restartHosts"
syn match   kojiPolicyValue    "restartVerify"
syn match   kojiPolicyValue    "runroot"
syn match   kojiPolicyValue    "saveFailedTree"
syn match   kojiPolicyValue    "shutdown"
syn match   kojiPolicyValue    "sleep"
syn match   kojiPolicyValue    "someMethod"
syn match   kojiPolicyValue    "subtask"
syn match   kojiPolicyValue    "tagBuild"
syn match   kojiPolicyValue    "tagNotification"
syn match   kojiPolicyValue    "vmExec"
syn match   kojiPolicyValue    "waitrepo"
syn match   kojiPolicyValue    "waittest"
syn match   kojiPolicyValue    "winbuild"
syn match   kojiPolicyValue    "wrapperRPM"

" Define the default highlighting.
" Only used when an item doesn't have highlighting yet
hi def link kojiPolicyComment	Comment
hi def link kojiPolicyTodo	Todo
hi def link kojiPolicyString	String
hi def link kojiPolicyTest       Keyword
hi def link kojiPolicyAction     Keyword
hi def link kojiPolicyPolicy     Constant
hi def link kojiPolicyValue      Constant
hi def link kojiPolicyOperator   Operator

let b:current_syntax = "kojipolicy"

" vim: ts=8 sw=2
