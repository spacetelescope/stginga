multiimage_layout = ['seq', {}, [
    'vbox',  {'name': 'top', 'width': 1520, 'height': 900},
    {'row': ['hbox', {'name': 'menu'}], 'stretch': 0},
    {'row': [
        'vpanel', {}, [
            'vbox', {},
            {'row': [
                'hpanel', {'name': 'hpnl'}, [
                    'ws', {'name': 'left', 'width': 300, 'group': 2}, [
                        ('Info', [
                            'vpanel', {}, [
                                'ws', {'name': 'uleft', 'height': 300,
                                       'show_tabs': False, 'group': 3}
                            ],
                            [
                                'ws', {'name': 'lleft', 'height': 430,
                                       'show_tabs': True, 'group': 3}
                            ]
                        ])
                    ]
                ],
                [
                    'vbox', {'name': 'main', 'width': 700},
                    {'row': [
                        'ws', {'wstype': 'tabs', 'name': 'channels',
                               'group': 1, 'use_toolbar': True}
                    ],
                     'stretch': 1
                    },
                    {'row': [
                        'ws', {'wstype': 'stack', 'name': 'cbar',
                               'group': 99}
                    ],
                     'stretch': 0
                    },
                    {'row': [
                        'ws', {'wstype': 'stack', 'name': 'readout',
                               'group': 99}
                    ],
                     'stretch': 0
                    },
                    {'row': [
                        'ws', {'wstype': 'stack', 'name': 'operations',
                               'group': 99}
                    ],
                     'stretch': 0
                    }
                ],
                [
                    'ws', {'name': 'right', 'width': 430, 'group': 2}, [
                        ('Dialogs', [
                            'ws', {'name': 'dialogs', 'group': 2}
                        ])
                    ]
                ]
            ],
             'stretch': 1}, [
                 'ws', {'name': 'toolbar', 'height': 40,
                        'show_tabs': False, 'group': 2}
             ]
        ],
        [
            'hbox', {'name': 'pstamps'}
        ],
    ]},
    {'row': [
        'hbox', {'name': 'status'}
    ],
     'stretch': 0
    }
]]


def pre_gui_config(ginga):
    # This is needed for MultiImage and MIPick
    ginga.set_layout(multiimage_layout)


def post_gui_config(ginga):
    pass
