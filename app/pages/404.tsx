import ErrorPage from "../components/ErrorPage";

export default function NotFound() {
  return <ErrorPage code="404" title="Page not found" message="The page you requested does not exist in this demo." />;
}
