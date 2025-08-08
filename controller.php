<?php

namespace App\Http\Controllers\Reportes;

use App\Exports\EmisionLicenciasExport;
use App\Exports\FormResponsesExport;
use App\Http\Controllers\Controller;
use App\Models\Action;
use App\Models\Component;
use App\Models\Form;
use App\Models\Message;
use App\Models\Procedure;
use App\Models\Request as ModelsRequest;
use App\Models\Request_state;
use App\Models\Request_state_record;
use App\Models\ResponseForm;
use App\Models\User;
use Barryvdh\DomPDF\Facade\Pdf;
use Carbon\Carbon;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Session;
use Illuminate\View\View;
use App\Models\Area;
use App\Models\Attached_files;
use App\Models\People;
use Illuminate\Foundation\Auth\User as AuthUser;
use Maatwebsite\Excel\Facades\Excel;

class ReportesController extends Controller
{

    //---------------------------------------------------------------------------------------------------------------------------------
    public function user_reports(): View
    {
        $data = array(
            'titulo' => 'Reporte de formularios por usuarios',
            'user' => Auth::user(),
            'desde' => Carbon::now()->subMonth()->toDateString(),
            'hasta' => Carbon::now()->toDateString(),
            'activo' => array(
                'li_reporte' => 'menu-is-opening menu-open',
                'mnu_reporte' => 'active',
                'mnu_usuario' => 'active',
                'mnu_demora' => '',
                'mnu_estado' => '',
                'mnu_periodo' => '',
                'mnu_forms' => '',
                'mnu_emision' => '',
                'mnu_adjuntos' => '',
                'mnu_repo_mapa' => '',
            ),
        );

        return view('admin.reports.user_reports_form', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_user_forms($inicio, $final, $form_id, $user_id = '')
    {
        $inicio = Carbon::parse($inicio)->startOfDay();
        $final = Carbon::parse($final)->endOfDay();
        $form = Form::find($form_id);
        $users_id = explode(',', str_replace('"', '', trim($form->assing_user_id, "[]")));
        $users = User::whereIn('id', $users_id)->get();

        if (!empty($user_id)) {
            $users = User::where('id', $user_id)->get();
        }

        foreach ($users as &$user) {
            $instancias = ResponseForm::select('instancia_id', 'created_at')
                ->where('form_id', $form_id)
                ->where('user_id', $user->id)
                ->whereBetween('created_at', [$inicio, $final])
                ->groupBy('instancia_id')
                ->get();

            $instancias_id = $instancias->pluck('instancia_id');

            $archivos = Attached_files::whereIn('instancia_id', $instancias_id)->get();

            $user->counter = $instancias->count();
            $user->archivos = $archivos->count();
            $user->total_size = $archivos->sum('size');
            $user->total_paginas = $archivos->sum('amount');
        }

        $users = $users->sortByDesc('counter')->values();

        return $users;
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_user_forms_pdf($inicio, $final, $form, $user_id = '')
    {
        $user = Auth::user();
        if ($user->current_role == (config('parametros.env.ROL_VISUALIZADOR'))) {
            $user_id = Auth::user()->id;
        }
        $data = array(
            'inicio' => $inicio,
            'final' => $final,
            'users' => $this->get_user_forms($inicio, $final, $form, $user_id),
            'form' => Form::find($form),
        );

        $pdf = PDF::loadView('admin.reports.tabla-formularios-usuarios-pdf', $data);
        $pdf->set_paper('letter', 'portrait');

        return $pdf->stream();
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_user_forms_xls($inicio, $final, $form, $user_id = '')
    {
        $user = Auth::user();
        if ($user->current_role == (config('parametros.env.ROL_VISUALIZADOR'))) {
            $user_id = Auth::user()->id;
        }
        $users = $this->get_user_forms($inicio, $final, $form, $user_id);
        $nombre = 'reporte_' . date('YmdHi') . '_forms_users.xlsx';

        return Excel::download(new FormResponsesExport($users, Form::find($form), $inicio, $final), $nombre);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_users(Request $request)
    {
        $user           = Auth::user();
        $inicio         = ((isset($request['inicio'])) ? date('Y-m-d', strtotime($request['inicio'])) : date('Y-m-d')) . ' 00:00:00';
        $final          = ((isset($request['final'])) ? date('Y-m-d', strtotime($request['final'])) : date('Y-m-d')) . ' 23:59:59';
        $form           = $request->form_id;
        $user_id        = '';
        if ($user->current_role == (config('parametros.env.ROL_VISUALIZADOR'))) {
            $user_id = Auth::user()->id;
        }
        $data           = array(
            'user'   => $user,
            'inicio' => $inicio,
            'final'  => $final,
            'form'   => $form,
            'users'  => $this->get_user_forms($inicio, $final, $form, $user_id),
        );

        return response(['html' => view('admin.reports.tabla_usuarios', $data)->render()], 200);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function pdf_users($inicio, $fin, $forms_removed = false, $users_inactive = false, $form_id)
    {
        $user = Auth::user();
        $periodo = date('Ymd', strtotime($inicio)) . '_' . date('Ymd', strtotime($fin));
        $data = [
            'user' => $user,
            'inicio' => $inicio,
            'fin' => $fin,
            'forms_removed' => $forms_removed,
            'users_inactive' => $users_inactive,
            'instancias' => $this->users_instance($inicio, $fin, false, $users_inactive, $form_id),
            'vista' => 'admin.reports.tabla_usuarios',
        ];
        if ($forms_removed) {
            $data['instancias_removed'] = $this->users_instance($inicio, $fin, $forms_removed, $users_inactive, $form_id);
            $data['forms_removed'] = true;
        }
        if ($user->current_role == (config('parametros.env.ROL_VISUALIZADOR'))) {
            $data['vista'] = 'admin.reports.tabla_usuario';
        }
        $pdf = PDF::loadView('admin.reports.reporte_usuarios', $data);

        return $pdf->download("reporte_$periodo.pdf");
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_demora($desde = '', $hasta = '')
    {
        // Convertir fechas a rangos con hora para evitar exclusiones por timestamp
        $desde = $desde ? date('Y-m-d 00:00:00', strtotime($desde)) : null;
        $hasta = $hasta ? date('Y-m-d 23:59:59', strtotime($hasta)) : null;

        $procedures = Procedure::where('procedure_status_id', 1)->get();
        $aux = [];

        // Rango de días desde HOY hacia atrás
        $rangos = [
            'req_1_5'   => ['-5 day', 'now'],
            'req_6_15'  => ['-15 day', '-6 day'],
            'req_16_30' => ['-30 day', '-16 day'],
            'req_31_60' => ['-60 day', '-31 day'],
            'req_61_90' => ['-90 day', '-61 day'],
            'req_91'    => ['-9999 day', '-91 day'], // más de 90 días
        ];

        foreach ($procedures as $procedure) {
            $tramites = (object) [];
            $tramites->name = $procedure->name;

            $total = 0;

            foreach ($rangos as $key => [$from, $to]) {
                $query = ModelsRequest::whereNull('finish_date')
                    ->where('procedure_id', $procedure->id)
                    ->when($desde && $hasta, function ($q) use ($desde, $hasta) {
                        $q->whereBetween('start_date', [$desde, $hasta]);
                    })
                    ->whereBetween('start_date', [
                        date('Y-m-d', strtotime($from)),
                        date('Y-m-d', strtotime($to))
                    ]);

                $tramites->{$key} = $query->count();
                $total += $tramites->{$key};
            }

            $tramites->x_request = $total;
            $aux[$procedure->name] = $tramites;
        }

        return collect($aux)->sortByDesc('x_request')->values();
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function demora(): View
    {
        $desde = date('Y-m-d', strtotime('-30 days'));
        $hasta = date('Y-m-d');

        $data = [
            'activo' => [
                'li_reporte' => 'menu-is-opening menu-open',
                'mnu_reporte' => 'active',
                'mnu_usuario' => '',
                'mnu_demora' => 'active',
                'mnu_estado' => '',
                'mnu_forms' => '',
                'mnu_emision' => '',
                'mnu_periodo' => '',
                'mnu_adjuntos' => '',
                'mnu_repo_mapa' => '',
            ],
            'tramites' => $this->get_demora($desde, $hasta),
            'desde'    => $desde,
            'hasta'    => $hasta,
        ];

        return view('admin.reports.reporte_demora', $data);
    }


    //---------------------------------------------------------------------------------------------------------------------------------
    public function demora_tabla(Request $request): View
    {
        $desde = $request->input('desde') ?? date('Y-m-d', strtotime('-30 days'));
        $hasta = $request->input('hasta') ?? date('Y-m-d');

        $data = [
            'tramites' => $this->get_demora($desde, $hasta),
            'desde'    => $desde,
            'hasta'    => $hasta,
        ];

        return view('admin.reports.tabla_reporte_demora', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function demora_pdf()
    {
        $data = [
            'tramites' => $this->get_demora(),
        ];

        $pdf = PDF::loadView('admin.reports.demora_pdf', $data);
        $pdf->set_paper('letter', 'landscape');

        return $pdf->download('reporte_' . date('Ymd') . '.pdf');
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_estado()
    {

        $requests = Request_state_record::select('request_id')->distinct()->get();

        $lasts = [];
        foreach ($requests as $request) {
            $aux = (object) [];
            $last = Request_state_record::select('request_state_records.*', 'request_states.description')
                ->where('request_state_records.request_id', $request->request_id)
                ->join('request_states', 'request_states.id', '=', 'request_state_records.request_status_id')
                ->orderByDesc('date')
                ->first();
            $aux->id = $last->id;
            $aux->request_id = $last->request_id;
            $aux->procedure_id = $last->procedure_id;
            $aux->user_id = $last->user_id;
            $aux->date = $last->date;
            $aux->request_status_id = $last->request_status_id;
            array_push($lasts, $last);
        }

        $procedures = Procedure::all();
        foreach ($procedures as $procedure) {
            foreach ($lasts as $request) {
                foreach (Request_state::all() as $status) {
                    if ($request->request_status_id == $status->id && $request->procedure_id == $procedure->id) {
                        $status = $request->request_status_id;
                        $procedure->$status += 1;
                    }
                }
            }
        }

        return $procedures;
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_solicitudes_por_estado($desde, $hasta)
    {
        $data = [];
        $data['desde'] = $desde;
        $data['hasta'] = $hasta;

        $query = ModelsRequest::with([
            'request_state_records' => function ($q) {
                $q->orderByDesc('date');
            },
        ]);

        if ($desde) {
            $query->whereDate('start_date', '>=', $desde);
        }
        if ($hasta) {
            $query->whereDate('start_date', '<=', $hasta);
        }

        $peticiones = $query->get();
        $estados = Request_state::withTrashed()->get();
        $procedures = Procedure::withTrashed()->get();

        // Inicialización
        $vecinos = [];
        $data['total_solicitudes'] = $peticiones->count();
        $data['tramites'] = $procedures->count();
        $data['total_por_estado'] = [];

        foreach ($estados as $estado) {
            $data['total_por_estado'][$estado->id] = 0;
        }

        // Estructura inicial de cada procedimiento
        foreach ($procedures as $procedure) {
            $data['procedures'][$procedure->id] = $procedure->attributesToArray();
            $data['procedures'][$procedure->id]['estados'] = [];

            foreach ($estados as $status) {
                $data['procedures'][$procedure->id]['estados'][$status->id] = 0;
            }
            $data['procedures'][$procedure->id]['estados']['total'] = 0;
        }

        foreach ($peticiones as $request) {
            $vecinos[$request->user_id] = true;

            if (!count($request->request_state_records)) {
                continue;
            }

            $last = $request->request_state_records[0];
            $pid = $last->procedure_id;
            $sid = $last->request_status_id;

            if (isset($data['procedures'][$pid])) {
                $data['procedures'][$pid]['estados']['total']++;
                $data['procedures'][$pid]['estados'][$sid]++;
            }

            if (isset($data['total_por_estado'][$sid])) {
                $data['total_por_estado'][$sid]++;
            }
        }

        $data['vecinos'] = count($vecinos);

        // Ordenar por total descendente
        $data['procedures'] = collect($data['procedures'])
            ->sortByDesc(fn($item) => $item['estados']['total'])
            ->values();

        return $data;
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function estado(Request $request)
    {
        // $procedures = Procedure::withTrashed()->get();
        $procedures = Procedure::withTrashed()->select('id', 'name', 'deleted_at')->get();

        if ($procedures->isEmpty()) {
            Session::flash('alert', 'No hay trámites disponibles para generar un reporte.');
            return redirect()->route('tramites.list');
        }

        $desde = $request->input('desde') ?? date('Y-m-d', strtotime('-30 days'));
        $hasta = $request->input('hasta') ?? date('Y-m-d');

        $data = $this->get_solicitudes_por_estado($desde, $hasta);

        // total users con rol vecino
        // $total_vecinos = 0;

        $roles_vecinos = [
            config('parametros.env.ROL_VECINO_1'),
            config('parametros.env.ROL_VECINO_2'),
            config('parametros.env.ROL_VECINO_3'),
            config('parametros.env.ROL_VECINO_4'),
        ];

        $data['total_vecinos'] = User::whereHas('roles', function ($query) use ($roles_vecinos) {
            $query->whereIn('name', $roles_vecinos);
        })->count();

        // $data['total_vecinos'] = $total_vecinos;

        $data['activo'] = [
            'li_reporte' => 'menu-is-opening menu-open',
            'mnu_reporte' => 'active',
            'mnu_usuario' => '',
            'mnu_demora' => '',
            'mnu_estado' => 'active',
            'mnu_forms' => '',
            'mnu_emision' => '',
            'mnu_periodo' => '',
            'mnu_adjuntos' => '',
        ];

        $data['desde'] = $desde;
        $data['hasta'] = $hasta;

        $data['estados'] = Request_state::all();
        return view('admin.reports.reporte_estado', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function formularios(): View
    {

        $data = [
            // 'procedures' => $this->get_estado(),
            // 'statuses' => Form::all(),
            'statuses' => $forms = Form::where(function ($query) {
                $query->whereNull('deleted_at')->orWhere('deleted_at', '');
            })->get(),
            'desde' => Carbon::now()->subMonth()->toDateString(),
            'hasta' => Carbon::now()->toDateString(),
            'activo' => [
                'li_reporte' => 'menu-is-opening menu-open',
                'mnu_reporte' => 'active',
                'mnu_usuario' => '',
                'mnu_demora' => '',
                'mnu_estado' => '',
                'mnu_forms' => 'active',
                'mnu_periodo' => '',
                'mnu_adjuntos' => '',
                'mnu_repo_mapa' => '',
            ],
        ];
        return view('admin.reports.reporte_periodoform', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function emision(): View
    {
        $data2 = array(
            'inicio' => Carbon::now()->subMonth()->toDateString(),
            'final' => Carbon::now()->toDateString(),
            'users' => $this->get_emision()
        );
        $data = array(
            'desde' => Carbon::now()->subMonth()->toDateString(),
            'hasta' => Carbon::now()->toDateString(),
            'users' => view('admin.reports.tabla-emision-licencia-conducir', $data2)->render(),
            'activo' => array(
                'li_reporte' => 'menu-is-opening menu-open',
                'mnu_reporte' => 'active',
                'mnu_usuario' => '',
                'mnu_demora' => '',
                'mnu_estado' => '',
                'mnu_forms' => '',
                'mnu_emision' => 'active',
                'mnu_periodo' => '',
                'mnu_adjuntos' => '',
                'mnu_repo_mapa' => '',
            ),
        );
        return view('admin.reports.reporte_emision', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function tabla_emision(Request $request)
    {
        $inicio = $request->inicio;
        $final = $request->final;
        $data = array(
            'inicio' => $inicio,
            'final' => $final,
            'users' => $this->get_emision($inicio, $final),
        );

        $html = view('admin.reports.tabla-emision-licencia-conducir', $data)->render();

        return response(['html' => $html], 200);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function emision_pdf($inicio, $final)
    {
        $data = array(
            'inicio' => $inicio,
            'final' => $final,
            'users' => $this->get_emision($inicio, $final),
        );

        $pdf = PDF::loadView('admin.reports.tabla-emision-licencia-conducir-pdf', $data);
        $pdf->set_paper('letter', 'portrait');

        return $pdf->stream();
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function emision_xls($inicio, $final)
    {

        $users = $this->get_emision($inicio, $final);
        $nombre = 'reporte_' . date('YmdHi') . '_emision_licencias.xlsx';

        return Excel::download(new EmisionLicenciasExport($users, $inicio, $final), $nombre);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_emision($inicio = '', $final = '')
    {
        $fecha_inicio = empty($inicio) ? Carbon::now()->subMonth()->format('Y-m-d') : $inicio;
        $fecha_final = empty($final) ? Carbon::now()->format('Y-m-d') : $final;
        $form = Form::find(26);
        $users_id = explode(',', str_replace('"', '', trim($form->assing_user_id, "[]")));
        $users = User::whereIn('id', $users_id)->get();

        foreach ($users as &$user) {
            $responses = ResponseForm::where(['key' => 'name_65008c1572ce1', 'user_id' => $user->id])
                ->whereBetween('value', [$fecha_inicio, $fecha_final])
                ->get();

            $instancias_id = $responses->pluck('instancia_id')->unique();

            $archivos = Attached_files::whereIn('instancia_id', $instancias_id)->get();

            $user->counter = $responses->count();
            $user->archivos = $archivos->count();
            $user->total_size = $archivos->sum('size');
            $user->total_paginas = $archivos->sum('amount');
        }

        $users = $users->sortByDesc('counter')->values();

        return $users;
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function periodo(): View
    {
        $inicio = date('Y-m-d', strtotime('-30 days'));
        $final  = date('Y-m-d');

        $data = [
            'inicio'  => $inicio,
            'final'   => $final,
            'activo'  => [
                'li_reporte'     => 'menu-is-opening menu-open',
                'mnu_reporte'    => 'active',
                'mnu_usuario'    => '',
                'mnu_demora'     => '',
                'mnu_estado'     => '',
                'mnu_forms'      => '',
                'mnu_periodo'    => 'active',
                'mnu_adjuntos'   => '',
                'mnu_repo_mapa'  => '',
            ],
        ];

        return view('admin.reports.reporte_periodo', $data);
    }


    //---------------------------------------------------------------------------------------------------------------------------------
    public function adjuntos(): View
    {

        $inicio = date('Y-m-d', strtotime('-30 days'));
        $final  = date('Y-m-d');
        $data = [
            'inicio'  => $inicio,
            'final'   => $final,
            'activo' => [
                'li_reporte' => 'menu-is-opening menu-open',
                'mnu_reporte' => 'active',
                'mnu_usuario' => '',
                'mnu_demora' => '',
                'mnu_estado' => '',
                'mnu_forms' => '',
                'mnu_emision' => '',
                'mnu_periodo' => '',
                'mnu_adjuntos' => 'active',
                'mnu_repo_mapa' => '',
            ],
        ];

        return view('admin.reports.reporte_adjuntos', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function repo_mapa(): View
    {

        $inicio = date('Y-m-d', strtotime('-30 days'));
        $final  = date('Y-m-d');

        $data = [
            'inicio'  => $inicio,
            'final'   => $final,
            'activo' => [
                'li_reporte' => 'menu-is-opening menu-open',
                'mnu_reporte' => 'active',
                'mnu_usuario' => '',
                'mnu_demora' => '',
                'mnu_estado' => '',
                'mnu_forms' => '',
                'mnu_emision' => '',
                'mnu_periodo' => '',
                'mnu_adjuntos' => '',
                'mnu_repo_mapa' => 'active',
            ],
        ];

        if (config('parametros.env.APP_INSTANCE') !== '0') {
            $estados = Request_state::all();
            $data['estados'] = $estados;
            // Puedes agregar más datos aquí si es necesario
        }


        return view('admin.reports.reporte_mapa', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function consulta_contador($tramite, $estado)
    {
        $sql = DB::select('
                SELECT
                    sub_consulta_2.request_status_id,
                    forms.id,
                    response_requests.instancia
                FROM (
                    SELECT
                        request_state_records.*
                    FROM
                        `request_state_records`
                    INNER JOIN (
                        SELECT
                            `request_id`,
                            MAX(`date`) AS fecha
                        FROM
                            `request_state_records`
                        GROUP BY
                            `request_id`
                    ) sub_consulta
                    ON
                        request_state_records.`request_id` = sub_consulta.`request_id`
                        AND request_state_records.`date` = sub_consulta.fecha
                ) AS sub_consulta_2
                INNER JOIN
                    `request_states`
                ON
                    sub_consulta_2.request_status_id = request_states.id
                INNER JOIN
                    `procedures`
                ON
                    sub_consulta_2.procedure_id = procedures.id
                INNER JOIN
                    `forms`
                ON
                    procedures.form_id = forms.id
                INNER JOIN
                    `response_requests`
                ON
                    sub_consulta_2.request_id = response_requests.request_id
                WHERE
                    sub_consulta_2.procedure_id = ?
                    AND request_states.id = ?
            ', [$tramite, $estado]);

        return $sql;
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_markers(Request $request)
    {
        $inicio = date('Y-m-d 00:00:00', strtotime($request->inicio));
        $final = date('Y-m-d 23:59:59', strtotime($request->final));

        $mapa = Component::where('code', 'map')->firstOrFail();


        if (config('parametros.env.APP_INSTANCE') != 0) {
            $tramite = Procedure::with('form')->find($request->tramite_id);
            $formId = $tramite->form_id;
        } else {
            $form = Form::findOrFail($request->tramite_id);
            $formId = $form->id;
        }


        $query = ResponseForm::where('form_id', $formId)
            ->where('component_id', $mapa->id)
            ->whereBetween('created_at', [$inicio, $final]);
        //aca pregunta por los estados
        if ($request->estado != '0') {
            $solicitudes = $this->consulta_contador($request->tramite_id, $request->estado);
            $instanciaIds = collect($solicitudes)->pluck('instancia')->all();
            $query->whereIn('instancia_id', $instanciaIds ?: [0]);
        }

        $responses = $query->with('user', 'form')->get();


        if ($responses->isNotEmpty()) {
            foreach ($responses as $response) {
                if (config('parametros.env.APP_INSTANCE') != 0 && isset($tramite)) {
                    $response->tramite = $tramite;
                }
            }
        }

        return $responses;
    }

    //---------------------------------------------------------------------------------------------------------------------------------

    public function drop_tramites(Request $request)
    {
        $name = $request->name ?? '';
        $mapa = Component::where('code', 'map')->first();

        if ($request->has('view') && $request->view == 'map') {
            if (config('parametros.env.APP_INSTANCE') == 1 || config('parametros.env.APP_INSTANCE') == 2) {
                $tramites = Procedure::select('procedures.*')
                    ->when(!empty($name), function ($query) use ($name) {
                        $query->where('procedures.name', 'LIKE', "%{$name}%");
                    })
                    ->join('component_forms', 'procedures.form_id', '=', 'component_forms.form_id')
                    ->where('component_forms.component_id', $mapa->id)
                    ->where('procedures.procedure_status_id', '1')
                    ->get();

                foreach ($tramites as $tramite) {
                    $tramite->name = ucwords($tramite->name);
                }

                $view = view('admin.reports.drop_tramites', ['tramites' => $tramites]);
            } else {
                $forms = Form::query()
                    ->when(!empty($name), function ($query) use ($name) {
                        $query->where('forms.tittle', 'LIKE', "%{$name}%");
                    })
                    ->join('component_forms', 'forms.id', '=', 'component_forms.form_id')
                    ->where('component_forms.component_id', $mapa->id)
                    ->where('forms.status', '!=', '0')
                    ->get();

                $view = view('admin.reports.drop_formularios', ['forms' => $forms]);
            }
        } else {
            $tramites = Procedure::query()
                ->when(!empty($name), function ($query) use ($name) {
                    $query->where('name', 'LIKE', "%{$name}%");
                })
                ->where('procedure_status_id', '1')
                ->get();

            $view = view('admin.reports.drop_tramites', ['tramites' => $tramites]);
        }

        return $view;
    }


    //---------------------------------------------------------------------------------------------------------------------------------
    public function drop_formularios(Request $request): View
    {
        $formularios = Form::where('tittle', 'LIKE', "%$request->name%")
            ->where(function ($query) {
                $query->whereNull('deleted_at')->orWhere('deleted_at', '');
            })
            ->get();

        foreach ($formularios as $formulario) {
            $formulario->tittle = ucwords($formulario->tittle);
        }

        return view('admin.reports.drop_formularios', ['forms' => $formularios]);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_periodo(Request $request)
    {

        $inicio = date('Y-m-d', strtotime($request->inicio));
        $final = date('Y-m-d', strtotime($request->final));

        $procedure = Procedure::find($request->tramite_id);
        $aux = [
            'titulo' => "Trámite: #$procedure->id - $procedure->name",
            'subtitulo' => 'Período: ' . date('d/m/Y', strtotime($request->inicio)) . ' - ' . date('d/m/Y', strtotime($request->final)),
            'label' => 'Cantidad de solicitudes por trámite',
        ];

        while ($inicio <= $final) {

            $respuestas = ModelsRequest::where('procedure_id', $request->tramite_id)
                ->where('created_at', 'LIKE', "$inicio%")
                ->count();

            array_push($aux, (object) ['fecha' => $inicio, 'cantidad' => $respuestas]);

            $new_date = new Carbon($inicio);
            $new_date->addDay();
            $inicio = date('Y-m-d', strtotime($new_date->toDateString()));
        }

        $aux = (object) $aux;
        foreach ($aux as $value) {
            if (isset($value->fecha)) {
                $value->fecha = date('d/m/Y', strtotime($value->fecha));
            }
        }
        $aux = (array) $aux;

        return array_values($aux);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_periodo_forms(Request $request)
    {

        $inicio = date('Y-m-d', strtotime($request->inicio));
        $final = date('Y-m-d', strtotime($request->final));

        $form = Form::find($request->form_id);
        $aux = [
            'titulo' => "Formulario: #$form->id - $form->tittle",
            'subtitulo' => 'Período: ' . date('d/m/Y', strtotime($request->inicio)) . ' - ' . date('d/m/Y', strtotime($request->final)),
            'label' => 'Cantidad de respuestas por formulario',
        ];

        while ($inicio <= $final) {

            $respuestas = ResponseForm::select('instancia_id', 'created_at')
                ->where('form_id', $request->form_id)
                ->where('created_at', 'LIKE', "$inicio%")
                ->distinct('instancia_id')
                ->count();

            array_push($aux, (object) ['fecha' => $inicio, 'cantidad' => $respuestas]);

            $new_date = new Carbon($inicio);
            $new_date->addDay();
            $inicio = date('Y-m-d', strtotime($new_date->toDateString()));
        }

        $aux = (object) $aux;
        foreach ($aux as $value) {
            if (isset($value->fecha)) {
                $value->fecha = date('d/m/Y', strtotime($value->fecha));
            }
        }
        $aux = (array) $aux;

        return array_values($aux);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_adjuntos(Request $request)
    {

        $inicio = date('Y-m-d', strtotime($request->inicio));
        $final = date('Y-m-d', strtotime($request->final));
        $procedure = Procedure::find($request->tramite_id);
        $aux = [
            'titulo' => "Trámite: #$procedure->id - $procedure->name",
            'subtitulo' => 'Período: ' . date('d/m/Y', strtotime($request->inicio)) . ' - ' . date('d/m/Y', strtotime($request->final)),
            'label' => 'Cantidad de adjuntos por trámite',
        ];
        while ($inicio <= $final) {
            $respuestas = ResponseForm::select('instancia_id')
                ->where('form_id', $procedure->form_id)
                ->where('created_at', 'LIKE', $inicio . '%')
                ->count();

            array_push($aux, (object) ['fecha' => $inicio, 'cantidad' => $respuestas]);

            $new_date = new Carbon($inicio);
            $new_date->addDay();
            $inicio = date('Y-m-d', strtotime($new_date->toDateString()));
        }

        $aux = (object) $aux;
        foreach ($aux as $value) {
            if (isset($value->fecha)) {
                $value->fecha = date('d/m/Y', strtotime($value->fecha));
            }
        }
        $aux = (array) $aux;

        return array_values($aux);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function estado_pdf(Request $request)
    {
        $desde = $request->input('desde');
        $hasta = $request->input('hasta');

        $data = $data = $this->get_solicitudes_por_estado($desde, $hasta);

        $pdf = PDF::loadView('admin.reports.estado_pdf', $data);
        $pdf->set_paper('letter', 'landscape');

        return $pdf->download('reporte_' . date('Ymd') . '.pdf');
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_solucitudes_tramite_estado($procedure, $status, $desde = null, $hasta = null)
    {
        $query = ModelsRequest::query();
        $query->where('procedure_id', $procedure);
        $query->with(['user', 'request_state_records' => function ($q) {
            $q->orderByDesc('date');
        }]);

        if ($desde) {
            $query->whereDate('start_date', '>=', $desde);
        }
        if ($hasta) {
            $query->whereDate('start_date', '<=', $hasta);
        }

        $all_solicitudes = $query->get();

        return $this->filter_requests_by_status($all_solicitudes, [$status]);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function ver_solucitudes_estado($procedure, $status, Request $request): View
    {

        $desde = $request->input('desde') ?? date('Y-m-d', strtotime('-30 days'));
        $hasta = $request->input('hasta') ?? date('Y-m-d');
        $data = [];
        $data['status'] = Request_state::where('id', $status)->withTrashed()->first();
        $data['procedure'] = Procedure::where('id', $procedure)->withTrashed()->first();
        $data['solicitudes'] = $this->get_solucitudes_tramite_estado($procedure, $status, $desde, $hasta);

        return view('admin.reports.reporte_solicitudes', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function request_estado_pdf($procedure, $status, Request $request)
    {
        $desde = $request->input('desde') ?? date('Y-m-d', strtotime('-30 days'));
        $hasta = $request->input('hasta') ?? date('Y-m-d');
        $data['status'] = Request_state::where('id', $status)->withTrashed()->first();
        $data['procedure'] = Procedure::where('id', $procedure)->withTrashed()->first();
        $data['solicitudes'] = $this->get_solucitudes_tramite_estado($procedure, $status, $desde, $hasta);

        $pdf = PDF::loadView('admin.reports.solicitudes_pdf', $data);
        $pdf->set_paper('letter', 'landscape');

        return $pdf->download('reporte_' . date('Ymd') . '.pdf');
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function show_request_modal(Request $request): View
    {
        if (config('parametros.env.APP_INSTANCE') == 1) {
            $instancias = ResponseForm::where('instancia_id', $request->datos['instancia'])->get();
            $request_id = $instancias[0]->response_request()->first()->request_id;
            $data = [
                'solicitud' => ModelsRequest::find($request_id),
                'estado' => Request_state_record::find($request_id)->request_state()->first(),
                'tramite' => (config('parametros.env.APP_INSTANCE') == 1) ? Procedure::find($request->datos['tramite']) : '',
                'form' => Form::find($request->datos['form']),
                'instancias' => $instancias,
            ];
            $view = 'tramitacion.request.request_showmodal';
        }
        if (config('parametros.env.APP_INSTANCE') == 0) {
            $instancias = ResponseForm::where('instancia_id', $request->datos['instancia'])
                ->with(['components_form'])
                ->get();
            $data = [
                'form' => Form::find($request->datos['form']),
                'instancias' => $instancias,
            ];
            // dd($instancias);
            $view = 'tramitacion.request.request_showmodal_form';
        }

        // dd($data);
        return view($view, $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function acciones(): View
    {
        $inicio = date('Y-m-d', strtotime('-30 days'));
        $final  = date('Y-m-d');

        $data = [
            'inicio'  => $inicio,
            'final'   => $final,
            'activo' => [
                'li_reporte' => 'menu-is-opening menu-open',
                'mnu_reporte' => 'active',
                'mnu_usuario' => '',
                'mnu_demora' => '',
                'mnu_estado' => '',
                'mnu_forms' => '',
                'mnu_emision' => '',
                'mnu_periodo' => '',
                'mnu_adjuntos' => '',
                'mnu_repo_mapa' => '',
                'mnu_repo_acciones' => 'active',
            ],
        ];

        return view('admin.reports.reporte_acciones', $data);
    }
    //---------------------------------------------------------------------------------------------------------------------------------
    //---------------------------------------------------------------------------------------------------------------------------------
    public function indicadores(Request $request)
    {

        $originalMemoryLimit = ini_get('memory_limit');
        $originalExecutionTime = ini_get('max_execution_time');

        $fecha_inicio = $request->input('fecha_inicio');
        $fecha_fin = $request->input('fecha_fin');

        if (!$fecha_inicio) $fecha_inicio = Carbon::now()->subDays(30)->format("Y-m-d");
        if (!$fecha_fin) $fecha_fin = Carbon::now()->format("Y-m-d");

        $rango_dias = Carbon::parse($fecha_inicio)->diffInDays(Carbon::parse($fecha_fin));
        if ($rango_dias > 180) {
            ini_set('memory_limit', '1G'); // Aumentar el límite de memoria a 1GB
            ini_set('max_execution_time', '300'); // Aumentar el tiempo de ejecución a 5 minutos
        }

        try {
            // todos los vecinos

            // vecinos creados en intervalo
            $vecinos_q1 = User::with('roles');
            $vecinos_q2 = clone $vecinos_q1;
            $agentes_q = clone $vecinos_q1;
            if ($fecha_inicio) $vecinos_q1->whereDate('created_at', '>=', $fecha_inicio);
            if ($fecha_fin) $vecinos_q1->whereDate('created_at', '<=', $fecha_fin);
            $vecinos_registrados = $vecinos_q1->get()->filter(fn($user) => $user->roles->whereIn('id', [5, 6, 7, 8]));

            $vecinos_q2->whereIn('id', $vecinos_registrados->pluck('id'));
            $vecinos_q2->with(['requests' => function ($q) use ($fecha_inicio, $fecha_fin) {
                $q->with(['request_state_records' => function ($q2) use ($fecha_inicio, $fecha_fin) {
                    $q2->whereDate('created_at', '>=', $fecha_inicio);
                    $q2->whereDate('created_at', '<=', $fecha_fin);
                }]);
                $q->whereHas('request_state_records', function ($q) use ($fecha_inicio, $fecha_fin) {
                    $q->whereDate('created_at', '>=', $fecha_inicio);
                    $q->whereDate('created_at', '<=', $fecha_fin);
                    $q->where('request_status_id', 2);
                });
            }]);
            $vecinos_q2->whereHas('requests.request_state_records', function ($q) use ($fecha_inicio, $fecha_fin) {
                $q->whereDate('created_at', '>=', $fecha_inicio);
                $q->whereDate('created_at', '<=', $fecha_fin);
                $q->where('request_status_id', 2);
            });
            $vecinos_con_solicitudes = $vecinos_q2->get()->filter(fn($user) => $user->roles->whereIn('id', [5, 6, 7, 8]));

            // mensajes de vecinos y agentes en intervalo
            // Definir la consulta base sin ejecutarla aún
            $mensajes_q = Message::with('emisor')
                ->whereDate('created_at', '>=', $fecha_inicio)
                ->whereDate('created_at', '<=', $fecha_fin);

            // Clonar la consulta para no modificar la original
            $mensajes_vecinos_q = clone $mensajes_q;
            $mensajes_agentes_q = clone $mensajes_q;

            // Aplicar filtros específicos a cada consulta
            $mensajes_vecinos_q->whereNotIn('current_role', ['administrador', 'agente', 'supervisor', 'visualizador', 'editor']);
            $mensajes_agentes_q->whereNotIn('current_role', ['vecino nivel 1', 'vecino nivel 2', 'vecino nivel 3', 'vecino nivel 4']);

            // Ejecutar las consultas solo una vez
            $mensajes_vecinos = $mensajes_vecinos_q->get();
            $mensajes_agentes = $mensajes_agentes_q->get();

            // Filtrar los mensajes no leídos en memoria
            $mensajes_vecinos_sin_leer = $mensajes_vecinos->filter(fn($msg) => !$msg->readd);
            $mensajes_agentes_sin_leer = $mensajes_agentes->filter(fn($msg) => !$msg->readd);


            $agentes = $agentes_q->get()->filter(fn($user) => $user->roles->whereIn('id', [4]));

            // solicitudes
            $solicitudes_q = ModelsRequest::with(['request_state_records' => function ($q) use ($fecha_inicio, $fecha_fin) {
                $q->whereDate('created_at', '>=', $fecha_inicio);
                $q->whereDate('created_at', '<=', $fecha_fin);
                $q->orderByDesc('created_at');
            }]);
            $solicitudes_q->whereHas('request_state_records', function ($q) use ($fecha_inicio, $fecha_fin) {
                $q->whereDate('created_at', '>=', $fecha_inicio);
                $q->whereDate('created_at', '<=', $fecha_fin);
                $q->where('request_status_id', 2);
            });
            $solicitudes_q->orderBy('created_at', 'asc');
            $solicitudes = $solicitudes_q->get();
            $solicitudes_estados = [
                3 => [], // en proceso
                4 => [], // finalizado
                5 => [], // rechazado
                6 => [] // revocado
            ];

            $dias_finalizacion = [];
            $dias_proceso = [];
            $dias_totales = 0;
            $promedio_finalizacion = 0;
            $promedio_solicitudes = 0;
            $promedio_proceso = 0;



            if (count($solicitudes) > 0) {
                $calc_fecha_i = $fecha_inicio ? Carbon::parse($fecha_inicio) : Carbon::parse($solicitudes->first()->created_at);
                $calc_fecha_f = $fecha_fin ? Carbon::parse($fecha_fin) : Carbon::now();

                $dias_totales = $calc_fecha_i->diffInDays($calc_fecha_f);

                // Para evitar división por 0, consideramos al menos 1 día
                $dias_totales = max($dias_totales, 1);

                $promedio_solicitudes = count($solicitudes) / $dias_totales;
            }

            $solicitudes_estados = [
                3 => [], // en proceso
                4 => [], // finalizado
                5 => [], // rechazado
                6 => []  // revocado
            ];

            // Filtrar y agrupar solicitudes
            $solicitudes->each(function ($solicitud) use (&$solicitudes_estados, &$dias_finalizacion, &$dias_proceso) {
                $last_record = $solicitud->request_state_records->first();
                $iniciada_record = $solicitud->request_state_records->firstWhere('request_status_id', 2);
                $proceso_record = $solicitud->request_state_records->firstWhere('request_status_id', 3);

                // Clasificación de estados
                if ($last_record && in_array($last_record->request_status_id, [3, 4, 5, 6])) {
                    $solicitudes_estados[$last_record->request_status_id][] = $solicitud;
                }

                // Calcular días de finalización
                if ($iniciada_record && $last_record && in_array($last_record->request_status_id, [4, 5, 6])) {
                    $dias_finalizacion[] = Carbon::parse($iniciada_record->created_at)
                        ->diffInDays(Carbon::parse($last_record->created_at));
                }

                // Calcular días en proceso
                if ($iniciada_record && $proceso_record) {
                    $dias_proceso[] = Carbon::parse($iniciada_record->created_at)
                        ->diffInDays(Carbon::parse($proceso_record->created_at));
                }
            });
            // Calcular promedios
            $promedio_finalizacion = collect($dias_finalizacion)->avg() ?? 0;
            $promedio_proceso = collect($dias_proceso)->avg() ?? 0;

            // Formatear los valores con 2 decimales
            $promedio_finalizacion = number_format($promedio_finalizacion, 2);
            $promedio_proceso = number_format($promedio_proceso, 2);


            $data = [];
            $data['fecha_inicio'] = $fecha_inicio;
            $data['fecha_fin'] = $fecha_fin;


            $data['total_vecinos_registrados'] = count($vecinos_registrados);

            $data['total_vecinos_con_solicitudes'] = count($vecinos_con_solicitudes);

            $data['total_mensajes_vecinos'] = count($mensajes_vecinos);

            $data['total_mensajes_vecinos_sin_leer'] = count($mensajes_vecinos_sin_leer);

            $data['agentes'] = $agentes;
            $data['agentes_total_mensajes'] = count($mensajes_agentes);
            $data['agentes_mensajes_sin_leer'] = count($mensajes_agentes_sin_leer);


            $data['total_solicitudes'] = count($solicitudes);
            $data['total_solicitudes_proceso'] = count($solicitudes_estados[3]);
            $data['total_solicitudes_finalizadas'] = count($solicitudes_estados[4]);
            $data['total_solicitudes_rechazadas'] = count($solicitudes_estados[5]) + count($solicitudes_estados[6]);

            $data["dias_totales"] = $dias_totales;
            $data["promedio_finalizacion"] = $this->formatearPromedio($promedio_finalizacion);
            $data["promedio_proceso"] = $this->formatearPromedio($promedio_proceso);
            $data["dias_finalizacion"] = $dias_finalizacion;
            $data["dias_proceso"] = $dias_proceso;
            $data["promedio_solicitudes"] = $this->formatearPromedio($promedio_solicitudes);

            $data['activo'] = [
                'li_reporte'    => 'menu-is-opening menu-open',
                'mnu_reporte'   => 'active',
                'mnu_usuario'   => '',
                'mnu_demora'    => '',
                'mnu_estado'    => '',
                'mnu_forms'     => '',
                'mnu_periodo'   => '',
                'mnu_adjuntos'  => '',
                'mnu_repo_mapa' => '',
                'mnu_repo_acciones' => '',
                'mnu_repo_indicadores' => 'active',
            ];

            return view('admin.reports.reporte_indicadores', $data);
        } catch (\Exception $e) {
            // Manejar errores
            return response(['error' => $e->getMessage()], 500);
        } finally {
            // Restaurar los valores originales
            ini_set('memory_limit', $originalMemoryLimit);
            ini_set('max_execution_time', $originalExecutionTime);
        }
    }
    //---------------------------------------------------------------------------------------------------------------------------------
    // public function indicadores(Request $request): View
    // {

    //     $originalMemoryLimit = ini_get('memory_limit');
    //     $originalExecutionTime = ini_get('max_execution_time');

    //     $fecha_inicio = $request->input('fecha_inicio');
    //     $fecha_fin = $request->input('fecha_fin');

    //     if (!$fecha_inicio) $fecha_inicio = Carbon::now()->subDays(180)->format("Y-m-d");
    //     if (!$fecha_fin) $fecha_fin = Carbon::now()->format("Y-m-d");

    //     $rango_dias = Carbon::parse($fecha_inicio)->diffInDays(Carbon::parse($fecha_fin));
    //     if ($rango_dias > 180) {
    //         // dd('entro');
    //         ini_set('memory_limit', '1G'); // Aumentar el límite de memoria a 1GB
    //         ini_set('max_execution_time', '300'); // Aumentar el tiempo de ejecución a 5 minutos
    //     }

    //     try {
    //         // todos los vecinos
    //         $vecinos_q = User::with('roles');
    //         $vecinos = $vecinos_q->get()->filter(fn($user) => $user->roles->whereIn('id', [5, 6, 7, 8]));

    //         // vecinos creados en intervalo
    //         $vecinos_q1 = User::with('roles');
    //         if ($fecha_inicio) $vecinos_q1->whereDate('created_at', '>=', $fecha_inicio);
    //         if ($fecha_fin) $vecinos_q1->whereDate('created_at', '<=', $fecha_fin);
    //         $vecinos_registrados = $vecinos_q1->get()->filter(fn($user) => $user->roles->whereIn('id', [5, 6, 7, 8]));

    //         // vecinos con solicitudes en intervalo
    //         $vecinos_q2 = User::with('roles');
    //         $vecinos_q2->whereIn('id', $vecinos_registrados->pluck('id'));
    //         $vecinos_q2->with(['requests' => function ($q) use ($fecha_inicio, $fecha_fin) {
    //             $q->with(['request_state_records' => function ($q2) use ($fecha_inicio, $fecha_fin) {
    //                 $q2->whereDate('created_at', '>=', $fecha_inicio);
    //                 $q2->whereDate('created_at', '<=', $fecha_fin);
    //             }]);
    //             $q->whereHas('request_state_records', function ($q) use ($fecha_inicio, $fecha_fin) {
    //                 $q->whereDate('created_at', '>=', $fecha_inicio);
    //                 $q->whereDate('created_at', '<=', $fecha_fin);
    //                 $q->where('request_status_id', 2);
    //             });
    //         }]);
    //         $vecinos_q2->whereHas('requests.request_state_records', function ($q) use ($fecha_inicio, $fecha_fin) {
    //             $q->whereDate('created_at', '>=', $fecha_inicio);
    //             $q->whereDate('created_at', '<=', $fecha_fin);
    //             $q->where('request_status_id', 2);
    //         });
    //         $vecinos_con_solicitudes = $vecinos_q2->get()->filter(fn($user) => $user->roles->whereIn('id', [5, 6, 7, 8]));

    //         // mensajes de vecinos en intervalo
    //         $mensajes_q = Message::with('emisor');
    //         // $mensajes_q->whereIn('emisor_id', $vecinos->pluck('id'));
    //         $mensajes_q->whereNotIn('current_role', ['administrador', 'agente', 'supervisor', 'visualizador', 'editor']);
    //         $mensajes_q->whereDate('created_at', '>=', $fecha_inicio);
    //         $mensajes_q->whereDate('created_at', '<=', $fecha_fin);
    //         $mensajes_vecinos = $mensajes_q->get();


    //         $mensajes_vecinos_sin_leer = [];
    //         foreach ($mensajes_vecinos as $msg) {
    //             if (!$msg->readd) $mensajes_vecinos_sin_leer[] = $msg;
    //         }

    //         // agentes
    //         $mensajes_a = Message::with('emisor');
    //         // $mensajes_q->whereIn('emisor_id', $vecinos->pluck('id'));
    //         $mensajes_a->whereNotIn('current_role', ['vecino nivel 1', 'vecino nivel 2', 'vecino nivel 3', 'vecino nivel 4']);
    //         $mensajes_a->whereDate('created_at', '>=', $fecha_inicio);
    //         $mensajes_a->whereDate('created_at', '<=', $fecha_fin);
    //         $mensajes_agentes = $mensajes_a->get();


    //         $mensajes_agentes_sin_leer = [];
    //         foreach ($mensajes_agentes as $msg) {
    //             if (!$msg->readd) $mensajes_agentes_sin_leer[] = $msg;
    //         }
    //         $agentes_q = User::with('roles');
    //         //lo comentado es lo de marce
    //         // $agentes_q->with(['sent_messages' => function ($sent_messages_query) use ($fecha_inicio, $fecha_fin) {
    //         //     $sent_messages_query->whereDate('created_at', '>=', $fecha_inicio);
    //         //     $sent_messages_query->whereDate('created_at', '<=', $fecha_fin);
    //         // }]);
    //         $agentes = $agentes_q->get()->filter(fn($user) => $user->roles->whereIn('id', [4]));

    //         // $agentes_total_mensajes = 0;
    //         // $agentes_mensajes_sin_leer = 0;
    //         // foreach ($agentes as $agente) {
    //         //     $agentes_total_mensajes += count($agente->sent_messages);
    //         //     foreach ($agente->sent_messages as $msg) {
    //         //         if (!$msg->readd) $agentes_mensajes_sin_leer += 1;
    //         //     }
    //         // }

    //         // solicitudes
    //         $solicitudes_q = ModelsRequest::with(['request_state_records' => function ($q) use ($fecha_inicio, $fecha_fin) {
    //             $q->whereDate('created_at', '>=', $fecha_inicio);
    //             $q->whereDate('created_at', '<=', $fecha_fin);
    //             $q->orderByDesc('created_at');
    //         }]);
    //         $solicitudes_q->whereHas('request_state_records', function ($q) use ($fecha_inicio, $fecha_fin) {
    //             $q->whereDate('created_at', '>=', $fecha_inicio);
    //             $q->whereDate('created_at', '<=', $fecha_fin);
    //             $q->where('request_status_id', 2);
    //         });
    //         $solicitudes_q->orderBy('created_at', 'asc');
    //         $solicitudes = $solicitudes_q->get();
    //         $solicitudes_estados = [
    //             3 => [], // en proceso
    //             4 => [], // finalizado
    //             5 => [], // rechazado
    //             6 => [] // revocado
    //         ];

    //         $dias_finalizacion = [];
    //         $dias_proceso = [];
    //         $dias_totales = 0;
    //         $promedio_finalizacion = 0;
    //         $promedio_solicitudes = 0;
    //         $promedio_proceso = 0;

    //         if (count($solicitudes) > 0) {
    //             $calc_fecha_i = $fecha_inicio ? Carbon::parse($fecha_inicio) : Carbon::parse($solicitudes->first()->created_at);
    //             $calc_fecha_f = $fecha_fin ? Carbon::parse($fecha_fin) : Carbon::now();
    //             $dias_totales = $calc_fecha_i->diffInDays($calc_fecha_f);
    //             $promedio_solicitudes = count($solicitudes) / $dias_totales;
    //             // $promedio_solicitudes = number_format(count($solicitudes) / $dias_totales);

    //         }

    //         foreach ($solicitudes as $solicitud) {
    //             $last_record = $solicitud->request_state_records[0];
    //             $iniciada_record = $solicitud->request_state_records->where('request_status_id', 2)->first();
    //             $proceso_record = $solicitud->request_state_records->where('request_status_id', 3)->first();

    //             if (in_array($last_record->request_status_id, [3, 4, 5, 6])) { // evitar posible error de status;
    //                 $solicitudes_estados[$last_record->request_status_id][] = $solicitud;
    //             }

    //             // para calculo promedio finalizado en dias
    //             if ($iniciada_record && in_array($last_record->request_status_id, [4, 5, 6])) {
    //                 $inicio = Carbon::parse($iniciada_record->created_at);
    //                 $final = Carbon::parse($last_record->created_at);
    //                 $dias_finalizacion[] = $inicio->diffInDays($final);
    //             }

    //             // para calculo promedio finalizado en dias
    //             if ($iniciada_record && $proceso_record) {
    //                 $inicio = Carbon::parse($iniciada_record->created_at);
    //                 $final = Carbon::parse($proceso_record->created_at);
    //                 $dias_proceso[] = $inicio->diffInDays($final);
    //             }
    //         }

    //         if (count($dias_finalizacion) > 0) {
    //             $total_dias = array_sum($dias_finalizacion);
    //             $promedio_finalizacion = number_format($total_dias / count($dias_finalizacion), 2);
    //         }

    //         if (count($dias_proceso) > 0) {
    //             $total_dias = array_sum($dias_proceso);
    //             $promedio_proceso = number_format($total_dias / count($dias_proceso), 2);
    //         }

    //         $data = [];
    //         $data['fecha_inicio'] = $fecha_inicio;
    //         $data['fecha_fin'] = $fecha_fin;

    //         // $data['vecinos_registrados'] = $vecinos_registrados;
    //         $data['total_vecinos_registrados'] = count($vecinos_registrados);
    //         // $data['vecinos_con_solicitudes'] = $vecinos_con_solicitudes;
    //         $data['total_vecinos_con_solicitudes'] = count($vecinos_con_solicitudes);
    //         // $data['mensajes_vecinos'] = $mensajes_vecinos;
    //         $data['total_mensajes_vecinos'] = count($mensajes_vecinos);
    //         // $data['mensajes_vecinos_sin_leer'] = $mensajes_vecinos_sin_leer;
    //         $data['total_mensajes_vecinos_sin_leer'] = count($mensajes_vecinos_sin_leer);

    //         $data['agentes'] = $agentes;
    //         $data['agentes_total_mensajes'] = count($mensajes_agentes);
    //         $data['agentes_mensajes_sin_leer'] = count($mensajes_agentes_sin_leer);

    //         // $data['solicitudes'] = $solicitudes;
    //         $data['total_solicitudes'] = count($solicitudes);
    //         // $data['solicitudes_estados'] = $solicitudes_estados;
    //         $data['total_solicitudes_proceso'] = count($solicitudes_estados[3]);
    //         $data['total_solicitudes_finalizadas'] = count($solicitudes_estados[4]);
    //         $data['total_solicitudes_rechazadas'] = count($solicitudes_estados[5]) + count($solicitudes_estados[6]);

    //         // $data["promedio_finalizacion"] = $promedio_finalizacion;
    //         // $data["promedio_proceso"] = $promedio_proceso;

    //         $data["dias_totales"] = $dias_totales;
    //         $data["promedio_finalizacion"] = $this->formatearPromedio($promedio_finalizacion);
    //         $data["promedio_proceso"] = $this->formatearPromedio($promedio_proceso);
    //         $data["dias_finalizacion"] = $dias_finalizacion;
    //         $data["dias_proceso"] = $dias_proceso;
    //         $data["promedio_solicitudes"] = $this->formatearPromedio($promedio_solicitudes);

    //         $data['activo'] = [
    //             'li_reporte'    => 'menu-is-opening menu-open',
    //             'mnu_reporte'   => 'active',
    //             'mnu_usuario'   => '',
    //             'mnu_demora'    => '',
    //             'mnu_estado'    => '',
    //             'mnu_forms'     => '',
    //             'mnu_periodo'   => '',
    //             'mnu_adjuntos'  => '',
    //             'mnu_repo_mapa' => '',
    //             'mnu_repo_acciones' => '',
    //             'mnu_repo_indicadores' => 'active',
    //         ];

    //         return view('admin.reports.reporte_indicadores', $data);
    //     } catch (\Exception $e) {
    //         // Manejar errores
    //         return response()->json(['error' => $e->getMessage()], 500);
    //     } finally {
    //         // Restaurar los valores originales
    //         ini_set('memory_limit', $originalMemoryLimit);
    //         ini_set('max_execution_time', $originalExecutionTime);
    //     }
    // }
    //---------------------------------------------------------------------------------------------------------------------------------
    public function totales_people(Request $request): View
    {
        $vecinos_q1 = User::with('roles');

        // $vecinos_registrados = $vecinos_q1->get()->filter(fn ($user) => $user->roles->whereIn('id', [5, 6, 7, 8]));
        $people = People::all();
        $vecinos_q2 = User::with(['roles' => function ($query) {
            $query->whereIn('id', [6, 7, 8]);
        }])
            ->whereNotNull('related_person')
            ->whereHas('roles', function ($query) {
                $query->whereIn('id', [6, 7, 8]);
            })
            ->get();

        $vecinos_q3 = User::with(['roles'])
            ->whereNotNull('related_person')
            ->whereDoesntHave('roles', function ($query) {
                $query->whereIn('id', [6, 7, 8]);
            })
            ->get();

        $total_usuarios_vinculados_validacion = $vecinos_q2->count();
        $total_usuarios_vinculados_sin_validacion = $vecinos_q3->count();
        // $data['vecinos_registrados'] = $vecinos_registrados;
        $usuarios_vinculados = User::whereNotNull('related_person')->count();
        $usuarios_no_vinculados = User::whereNull('related_person')->count();
        $people_vinculado = People::whereNotNull('user_id')->count();

        $conteos_iguales = ($usuarios_vinculados === $people_vinculado) ? true : false;
        // true - si coincide vinculaciones
        $data['total_vecinos_registrados'] = count($vecinos_q1->get());
        $data['total_people'] = count($people);
        $data['total_usuarios_vinculados'] = $usuarios_vinculados;
        $data['total_usuarios_no_vinculados'] = $usuarios_no_vinculados;
        $data['total_usuarios_vinculados_validacion'] = $total_usuarios_vinculados_validacion;
        $data['total_usuarios_vinculados_sin_validacion'] = $total_usuarios_vinculados_sin_validacion;


        $data['activo'] = [
            'li_reporte'    => 'menu-is-opening menu-open',
            'mnu_reporte'   => 'active',
            'mnu_usuario'   => '',
            'mnu_demora'    => '',
            'mnu_estado'    => '',
            'mnu_forms'     => '',
            'mnu_periodo'   => '',
            'mnu_adjuntos'  => '',
            'mnu_repo_mapa' => '',
            'mnu_repo_acciones' => '',
            'mnu_repo_people' => 'active',
        ];

        return view('admin.reports.reporte_people', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_acciones(Request $request)
    {
        $acciones = Action::where('procedure_id', $request->tramite_id)->get();
        $acciones_count = [];
        foreach ($acciones as $accion) {
            $acciones_count[$accion->id] = [
                'description' => $accion->description,
                'requests' => [],
            ];
        }

        $query = ModelsRequest::query();
        $query->where('procedure_id', $request->tramite_id);
        $query->with(['requests_action' => function ($request_action) {
            $request_action->with(['action']);
            $request_action->orderByDesc('created_at');
        }]);
        $query->with(['request_state_records' => function ($request_state_records) {
            $request_state_records->orderByDesc('created_at');
        }]);
        $query->whereBetween('created_at', [$request->inicio, $request->final]);
        $all_request = $query->get();

        $requests = $this->filter_requests_by_status($all_request, [2, 3]);

        foreach ($requests as $request) {
            if (!$request->requests_action || count($request->requests_action) === 0) {
                continue;
            }
            $last_action = $request->requests_action[0];
            $acciones_count[$last_action->action->id]['requests'][] = $request;
        }

        return $acciones_count;
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    private function filter_requests_by_status($all_solicitudes, $estados)
    {
        // filtro por estado del ultimo registro
        $solicitudes = [];
        foreach ($all_solicitudes as $solicitud) {
            if (!count($solicitud->request_state_records)) {
                continue;
            }
            $last_status = $solicitud->request_state_records[0];

            foreach ($estados as $estado) {
                if ($last_status->request_status_id == $estado) {
                    $solicitudes[] = $solicitud;

                    continue;
                }
            }
        }

        return $solicitudes;
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function solicitudes_area(): View
    {
        $data = array(
            'activo' => array(
                'li_reporte'        => 'menu-is-opening menu-open',
                'mnu_reporte'       => 'active',
                'mnu_usuario'       => '',
                'mnu_demora'        => '',
                'mnu_estado'        => '',
                'mnu_forms'         => '',
                'mnu_periodo'       => '',
                'mnu_adjuntos'      => '',
                'mnu_repo_mapa'     => '',
                'mnu_repo_acciones' => '',
                'mnu_repo_area'     => 'active',
            ),
            'default_date'      => date('Y-m-d', strtotime(Carbon::now()->subDays(30)->toString())),
        );

        $data['date'] = now()->format('Y-m-d');
        return view('admin.reports.reporte_area', $data);
    }

    public function get_areas(Request $request)
    {
        $name = $request->input('name', '');

        $areas = Area::when($name, function ($query, $name) {
            $query->where('descripcion', 'LIKE', "%{$name}%");
        })->get(['id', 'descripcion']); // Solo traemos lo necesario

        return response()->json($areas);
    }



    //---------------------------------------------------------------------------------------------------------------------------------
    public function solicitudes_todas_areas(): View
    {
        $areas = Area::all();

        $data = array(
            'activo' => array(
                'li_reporte'           => 'menu-is-opening menu-open',
                'mnu_reporte'          => 'active',
                'mnu_usuario'          => '',
                'mnu_demora'           => '',
                'mnu_estado'           => '',
                'mnu_forms'            => '',
                'mnu_periodo'          => '',
                'mnu_adjuntos'         => '',
                'mnu_repo_mapa'        => '',
                'mnu_repo_acciones'    => '',
                'mnu_repo_area'        => '',
                'mnu_repo_todas_areas' => 'active',
            ),
            'default_date'      => date('Y-m-d', strtotime(Carbon::now()->subMonth()->toString())),
        );

        $data['areas'] = $areas;
        return view('admin.reports.reporte_todas_areas', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_solicitudes_area(Request $request)
    {
        $areaId = $request->areaId;
        $inicio = $request->inicio;
        $final = $request->final;

        // busco el area correspondiente con sus tramites
        $area = Area::with('procedures')->find($areaId);
        $tramites = $area->procedures;

        // traer solicitudes de cada tramite
        $solicitudes_q = ModelsRequest::with(['request_state_records' => function ($q) use ($inicio, $final) {
            $q->whereDate('created_at', '>=', $inicio);
            $q->whereDate('created_at', '<=', $final);
            $q->orderByDesc('created_at');
        }]);
        $solicitudes_q->whereHas('request_state_records', function ($q) use ($inicio, $final) {
            $q->whereDate('created_at', '>=', $inicio);
            $q->whereDate('created_at', '<=', $final);
            $q->where('request_status_id', 2);
        });
        $solicitudes_q->whereIn('procedure_id', $tramites->pluck('id'));
        $solicitudes = $solicitudes_q->get();


        $data = [];
        // clasifico los tramites
        foreach ($tramites as $tramite) {
            $data[$tramite->id] = [
                "name" => $tramite->name,
                "solicitudes" => [
                    2 => [], // iniciada
                    3 => [], // en proceso
                    4 => [], // finalizado
                ]
            ];
        }

        // clasifico y acumulo las solicitudes
        foreach ($solicitudes as $solicitud) {
            $last_record = $solicitud->request_state_records[0];
            $status = $last_record->request_status_id;
            if (!in_array($status, [2, 3, 4])) continue;

            // append solicitude segun corresponda al status
            $data[$solicitud->procedure_id]["solicitudes"][$status][] = $solicitud;
        }

        return $data;
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    //   public function get_solicitudes_todas_areas(Request $request) {

    //     $inicio  = Carbon::parse($request->inicio)->startOfDay();
    //     $final   = Carbon::parse($request->final)->endOfDay();
    //     $estados = ['publicado', 'en proceso', 'finalizado'];

    //     $results = DB::table('requests as r')
    //       ->join(DB::raw('
    //         (
    //             SELECT request_id, MAX(date) as max_date
    //             FROM request_state_records
    //             GROUP BY request_id
    //         ) as latest'), function ($join) {
    //         $join->on('r.id', '=', 'latest.request_id');
    //       })
    //       ->join('request_state_records as rsr', function ($join) {
    //         $join->on('rsr.request_id', '=', 'r.id')
    //           ->on('rsr.date', '=', 'latest.max_date');
    //       })
    //       ->join('request_states as rs', 'rs.id', '=', 'rsr.request_status_id')
    //       ->join('procedures as p', 'p.id', '=', 'r.procedure_id')
    //       ->join('areas as a', 'a.id', '=', 'p.area_id')
    //       ->whereBetween('r.start_date', [$inicio, $final])
    //       ->whereIn('rs.description', $estados)
    //       ->select('a.descripcion as area', 'rs.description as estado', DB::raw('COUNT(*) as cantidad'))
    //       ->groupBy('a.descripcion', 'rs.description')
    //       ->get()
    //       ->groupBy('area')
    //       ->map(function ($group) {
    //         return $group->pluck('cantidad', 'estado')->mapWithKeys(function ($value, $key) {
    //           $key_normalizado = strtolower(trim($key));
    //           $key_final = ($key_normalizado === 'publicado') ? 'Iniciado' : ucfirst($key);
    //           return [$key_final => $value];
    //         });
    //       })
    //       ->toArray();

    //     return response($results, 200);
    //   }

    //---------------------------------------------------------------------------------------------------------------------------------

    public function get_solicitudes_todas_areas(Request $request)
    {
        $inicio  = Carbon::parse($request->inicio)->startOfDay();
        $final   = Carbon::parse($request->final)->endOfDay();
        $estados = ['publicado', 'en proceso', 'finalizado'];

        // Subconsulta para obtener el último movimiento por solicitud
        $latestMovements = DB::table('movements')
            ->select('movements.request_id', 'movements.area_to', DB::raw('ROW_NUMBER() OVER (PARTITION BY request_id ORDER BY created_at DESC) as rn'));

        $results = DB::table('requests as r')
            ->join(DB::raw('
            (
                SELECT request_id, MAX(date) as max_date
                FROM request_state_records
                GROUP BY request_id
            ) as latest'), function ($join) {
                $join->on('r.id', '=', 'latest.request_id');
            })
            ->join('request_state_records as rsr', function ($join) {
                $join->on('rsr.request_id', '=', 'r.id')
                    ->on('rsr.date', '=', 'latest.max_date');
            })
            ->join('request_states as rs', 'rs.id', '=', 'rsr.request_status_id')
            ->join('procedures as p', 'p.id', '=', 'r.procedure_id')

            // Left join con último movimiento
            ->leftJoinSub($latestMovements, 'lm', function ($join) {
                $join->on('r.id', '=', 'lm.request_id')->where('lm.rn', '=', 1);
            })

            // Área del movimiento (si hay), si no, la del procedimiento
            ->leftJoin('areas as area_movement', 'lm.area_to', '=', 'area_movement.id')
            ->leftJoin('areas as area_procedure', 'p.area_id', '=', 'area_procedure.id')

            ->whereBetween('r.created_at', [$inicio, $final])
            ->whereIn('rs.description', $estados)

            ->select(
                DB::raw('COALESCE(area_movement.descripcion, area_procedure.descripcion) as area'),
                'rs.description as estado',
                DB::raw('COUNT(*) as cantidad')
            )
            ->groupBy(DB::raw('COALESCE(area_movement.descripcion, area_procedure.descripcion)'), 'rs.description')
            ->get()
            ->groupBy('area')
            ->map(function ($group) {
                return $group->pluck('cantidad', 'estado')->mapWithKeys(function ($value, $key) {
                    $key_normalizado = strtolower(trim($key));
                    $key_final = ($key_normalizado === 'publicado') ? 'Iniciado' : ucfirst($key);
                    return [$key_final => $value];
                });
            })
            ->toArray();

        return response($results, 200);
    }



    //---------------------------------------------------------------------------------------------------------------------------------
    function formatearPromedio($valor)
    {
        if ($valor < 1) {
            return "Menos de 1";
        } elseif (is_numeric($valor) && floor($valor) == $valor) {
            // Si el número es entero (redondo), mostrar sin decimales
            return number_format($valor, 0);
        } else {
            // Si tiene decimales, mostrar solo la parte entera con "Más de"
            return "Más de " . floor($valor);
        }
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function actuaciones(): View
    {
        $inicio = date('Y-m-d', strtotime('-31 days'));
        $final  = date('Y-m-d');

        $data = [
            'inicio'  => $inicio,
            'final'   => $final,
            'activo'  => [
                'li_reporte'     => 'menu-is-opening menu-open',
                'mnu_reporte'    => 'active',
                'mnu_usuario'    => '',
                'mnu_demora'     => '',
                'mnu_estado'     => '',
                'mnu_forms'      => '',
                'mnu_periodo'    => '',
                'mnu_actuaciones'    => 'active',
                'mnu_adjuntos'   => '',
                'mnu_repo_mapa'  => '',
            ],
        ];

        return view('admin.reports.reporte_actuaciones', $data);
    }

    //---------------------------------------------------------------------------------------------------------------------------------
    public function get_actuaciones(Request $request)
    {
        $inicio = date('Y-m-d', strtotime($request->inicio));
        $final = date('Y-m-d', strtotime($request->final));

        $procedure = Procedure::find($request->tramite_id);
        $aux = [
            'titulo' => "Trámite: #$procedure->id - $procedure->name",
            'subtitulo' => 'Período: ' . date('d/m/Y', strtotime($request->inicio)) . ' - ' . date('d/m/Y', strtotime($request->final)),
            'label' => 'Cantidad de actuaciones por trámite',
        ];

        while ($inicio <= $final) {
            // Buscar actuaciones para el día
            $cantidad = DB::table('performances')
                ->join('requests', 'performances.request_id', '=', 'requests.id')
                ->where('requests.procedure_id', $request->tramite_id)
                ->whereDate('performances.created_at', $inicio)
                ->distinct('performances.request_id') //por si quieren que cuente solo una vez la actuación por solicitud
                ->count();

            array_push($aux, (object) ['fecha' => $inicio, 'cantidad' => $cantidad]);

            $inicio = date('Y-m-d', strtotime($inicio . ' +1 day'));
        }

        // Formatear fechas
        foreach ($aux as $value) {
            if (isset($value->fecha)) {
                $value->fecha = date('d/m/Y', strtotime($value->fecha));
            }
        }

        return array_values((array) $aux);
    }

    public function get_agentes_por_tramite(Request $request)
    {
        $inicio = $request->input('inicio');
        $final = $request->input('final');
        $procedure_id = $request->input('procedure_id');

        $usuarios = User::whereHas('roles', function ($query) {
            $query->whereIn('name', [
                config('parametros.env.ROL_AGENTE'),
                config('parametros.env.ROL_SUPERVISOR')
            ]);
        })->orderBy('surname')->orderBy('name')->get();

        $resultados = [];

        foreach ($usuarios as $usuario) {
            $conteo = [
                'en_proceso' => 0,
                'finalizados' => 0,
                'rechazados' => 0,
                'revocados' => 0,
            ];

            // Buscar los cambios de estado hechos por el usuario en el trámite
            $registros_estado = DB::table('request_state_records')
                ->join('requests', 'request_state_records.request_id', '=', 'requests.id')
                ->where('requests.procedure_id', $procedure_id)
                ->where('request_state_records.user_id', $usuario->id)
                ->where('request_state_records.created_at', '>=', $inicio . ' 00:00:00')
                ->where('request_state_records.created_at', '<=', $final . ' 23:59:59')
                ->select('request_state_records.request_status_id')
                ->get();

            foreach ($registros_estado as $registro) {
                match ((int)$registro->request_status_id) {
                    3 => $conteo['en_proceso']++,
                    4 => $conteo['finalizados']++,
                    5 => $conteo['rechazados']++,
                    6 => $conteo['revocados']++,
                    default => null,
                };
            }

            // Contar actuaciones
            $actuaciones = DB::table('performances')
                ->join('requests', 'performances.request_id', '=', 'requests.id')
                ->where('requests.procedure_id', $procedure_id)
                ->where('performances.user_id', $usuario->id)
                // ->whereBetween('performances.created_at', [$inicio, $final])
                ->count();

            $total = array_sum($conteo) + $actuaciones;

            $resultados[] = [
                'id' => $usuario->id,
                'usuario' => "{$usuario->surname}, {$usuario->name}",
                'en_proceso' => $conteo['en_proceso'],
                'finalizados' => $conteo['finalizados'],
                'rechazados' => $conteo['rechazados'],
                'revocados' => $conteo['revocados'],
                'actuaciones' => $actuaciones,
                'total' => $total, // para ordenamiento
            ];
        }

        usort($resultados, function ($a, $b) {
            $totalA = $a['en_proceso'] + $a['finalizados'] + $a['rechazados'] + $a['revocados'] + $a['actuaciones'];
            $totalB = $b['en_proceso'] + $b['finalizados'] + $b['rechazados'] + $b['revocados'] + $b['actuaciones'];
            return $totalB <=> $totalA; // orden descendente
        });
        return response()->json($resultados);
    }



    public function reporte_agentes_tramite(): View
    {
        $inicio = date('Y-m-d', strtotime('-31 days'));
        $final  = date('Y-m-d');
        return view('admin.reports.reporte_agentes_tramite', [
            'activo' => [
                'li_reporte' => 'menu-is-opening menu-open',
                'mnu_reporte' => 'active',
                'mnu_usuario'    => '',
                'mnu_demora'     => '',
                'mnu_estado'     => '',
                'mnu_forms'      => '',
                'mnu_periodo'    => '',
                'mnu_actuaciones'    => '',
                'mnu_adjuntos'   => '',
                'mnu_repo_mapa'  => '',
                'mnu_repo_agentes_tramite' => 'active',
            ],
            'inicio' =>  $inicio,
            'final' => $final,
            'procedures' => Procedure::select('id', 'name')->orderBy('name')->get(),
        ]);
    }
}

