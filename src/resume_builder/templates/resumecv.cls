% ============================================================================
% resumecv.cls - Minimal custom resume class
% Compatible with moderncv-style commands, with safe microtype/fontawesome use
% ============================================================================

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resumecv}[2024/11/10 Custom Resume Class v1.0]

% ---------------- Engine-safe guards for pdfTeX primitives ------------------
\newif\ifrcv@pdftex
\ifx\pdfprotrudechars\undefined
  \rcv@pdftexfalse
\else
  \rcv@pdftextrue
\fi
\ifrcv@pdftex
  \pdfprotrudechars=0\relax
  \pdfadjustspacing=0\relax
\fi

% -------------------------- Base class & options ----------------------------
\DeclareOption{sans}{\PassOptionsToClass{}{article}\AtEndOfClass{\renewcommand{\familydefault}{\sfdefault}}}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[11pt,a4paper]{article}

% ------------------------------ Required pkgs -------------------------------
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage{lmodern}
\RequirePackage[margin=1.5cm]{geometry}
\RequirePackage{xcolor}
\PassOptionsToPackage{hyphens}{url}
\RequirePackage[hidelinks]{hyperref}
\RequirePackage{enumitem}
\RequirePackage{multicol}
\RequirePackage{ragged2e}
\RequirePackage{needspace}

% microtype: keep expansion/protrusion off; safe with FA5
\RequirePackage[expansion=false,protrusion=false]{microtype}
\ifrcv@pdftex
  \pdfprotrudechars=0\relax
  \pdfadjustspacing=0\relax
\fi

% ------------------------------ Internals -----------------------------------
\makeatletter  % <-- REQUIRED for @ macros

% Style tokens (color applies; style kept for compatibility)
\newcommand{\@cvstyle}{banking}
\newcommand{\@cvcolor}{black}
\newcommand{\moderncvstyle}[1]{\renewcommand{\@cvstyle}{#1}}
\newcommand{\moderncvcolor}[1]{\renewcommand{\@cvcolor}{#1}}

% Make \nopagenumbers actually do something
\newcommand{\nopagenumbers}{\pagestyle{empty}}

% Identity storage
\newcommand{\@firstname}{}
\newcommand{\@familyname}{}
\newcommand{\@email}{}
\newcommand{\@phone}{}
\newcommand{\@address}{}
\newcommand{\@homepage}{}
\newcommand{\@linkedin}{}
\newcommand{\@github}{}

\newcommand{\firstname}[1]{\renewcommand{\@firstname}{#1}}
\newcommand{\familyname}[1]{\renewcommand{\@familyname}{#1}}
\newcommand{\name}[2]{\renewcommand{\@firstname}{#1}\renewcommand{\@familyname}{#2}}
\newcommand{\email}[1]{\renewcommand{\@email}{#1}}
\newcommand{\phone}[1]{\renewcommand{\@phone}{#1}}
\newcommand{\address}[1]{\renewcommand{\@address}{#1}}
\newcommand{\homepage}[1]{\renewcommand{\@homepage}{#1}}

% Social links
\newcommand{\social}[2][]{%
  \def\@socialtype{#1}%
  \def\@linkedinstr{linkedin}%
  \def\@githubstr{github}%
  \ifx\@socialtype\@linkedinstr
    \renewcommand{\@linkedin}{#2}%
  \fi
  \ifx\@socialtype\@githubstr
    \renewcommand{\@github}{#2}%
  \fi
}

% Title block
\newcommand{\makecvtitle}{%
  \begin{center}%
    {\Huge\bfseries\textcolor{\@cvcolor}{\@firstname\ \@familyname}}\\[0.5em]%
    \def\@hascontact{0}%
    \ifx\@email\empty\else \@email \def\@hascontact{1}\fi
    \ifx\@phone\empty\else \ifnum\@hascontact=1\ \textbar\ \fi \@phone \def\@hascontact{1}\fi
    \ifx\@address\empty\else \ifnum\@hascontact=1\ \textbar\ \fi \@address \def\@hascontact{1}\fi
    \ifnum\@hascontact=1\\[0.3em]\fi
    \def\@hassocial{0}%
    \ifx\@homepage\empty\else \href{\@homepage}{\@homepage}\def\@hassocial{1}\fi
    \ifx\@linkedin\empty\else \ifnum\@hassocial=1\ \textbar\ \fi \href{https://www.linkedin.com/in/\@linkedin}{\@linkedin}\def\@hassocial{1}\fi
    \ifx\@github\empty\else \ifnum\@hassocial=1\ \textbar\ \fi \href{https://github.com/\@github}{\@github}\def\@hassocial{1}\fi
  \end{center}%
  \vspace{1em}%
}

% cventry: {dates}{title}{organization}{location}{(unused)}{description}
\newcommand{\cventry}[6]{%
  \vspace{0.5em}%
  \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}l@{\extracolsep{0pt}}r}%
    \textbf{#3} & \textit{#1}\\% 
    \textit{#2} & \textit{#4}%
  \end{tabular*}%
  \ifx&#6&\else\\[0.3em]%
    {\small #6}%  % no minipage: allows page breaks
  \fi
  \par\vspace{0.5em}%
}

% cvitem: {label}{description}
\newcommand{\cvitem}[2]{%
  \vspace{0.3em}%
  \begin{description}[leftmargin=2em,style=nextline]%
    \item[\textbf{#1}] #2%
  \end{description}%
}

% Section style - tighter spacing to fit more content, unnumbered by default
\setcounter{secnumdepth}{0}  % Disable section numbering globally
\renewcommand{\section}{%
  \@startsection{section}{1}{\z@}%
  {-1ex \@plus -0.5ex \@minus -.1ex}%
  {0.5ex \@plus .1ex}%
  {\normalfont\Large\bfseries\color{\@cvcolor}}%
}

% Page setup - tighter spacing
\pagestyle{empty}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.25em}
\raggedbottom  % Allow flexible page breaking to reduce gaps

% Hyperref configuration
\hypersetup{
  colorlinks=true,
  linkcolor=\@cvcolor,
  urlcolor=blue,
  citecolor=\@cvcolor,
  pdfborder={0 0 0}
}
\Urlmuskip=0mu plus 1mu  % Allow URL breaking with minimal penalty

\makeatother  % <-- close @-scope
\endinput
